from django.db import models
from core.models import Interest, StudyField
from django.db.models import Q
from django.core.validators import MinValueValidator
from decimal import Decimal
from datetime import date, datetime, timedelta,time
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.contrib.auth import get_user_model
import os
import logging
from core.validators import syrian_phone_validator
logger = logging.getLogger(__name__)

User = get_user_model()
class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    
    def __str__(self):
        return f"{self.name}"
    class Meta:
        ordering = ['name']  


class CourseType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='course_types')
    
    def __str__(self):
        return f"{self.name}"
    
    def add_interest_tag(self, interest):
        """Add an interest tag to this course type"""
        CourseTypeTag.objects.get_or_create(
            course_type=self,
            interest=interest,
            study_field=None
        )
    
    def add_study_field_tag(self, study_field):
        """Add a study field tag to this course type"""
        CourseTypeTag.objects.get_or_create(
            course_type=self,
            interest=None,
            study_field=study_field
        )
    
    def remove_interest_tag(self, interest):
        """Remove an interest tag from this course type"""
        CourseTypeTag.objects.filter(
            course_type=self,
            interest=interest,
            study_field=None
        ).delete()
    
    def remove_study_field_tag(self, study_field):
        """Remove a study field tag from this course type"""
        CourseTypeTag.objects.filter(
            course_type=self,
            interest=None,
            study_field=study_field
        ).delete()
    
    def get_tags(self):
        """Get all tags for this course type"""
        return {
            'interests': list(self.tags.filter(interest__isnull=False).values_list('interest__name', flat=True)),
            'study_fields': list(self.tags.filter(study_field__isnull=False).values_list('study_field__name', flat=True))
        }
class CourseTypeTag(models.Model):
    course_type = models.ForeignKey(CourseType, on_delete=models.CASCADE, related_name='tags')
    interest = models.ForeignKey(Interest, on_delete=models.CASCADE, null=True, blank=True)
    study_field = models.ForeignKey(StudyField, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        unique_together = ('course_type', 'interest', 'study_field')

    def __str__(self):
        return f"{self.course_type.name} - {self.interest or self.study_field}"

class Hall(models.Model):
    name = models.CharField(max_length=100, unique=True)
    capacity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Must be at least 1"
    )
    location = models.CharField(max_length=255)
    hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text="Must be at least 0.01"
    )
    
    def __str__(self):
        return f"{self.name} ({self.location})"
    
    def clean(self):
        """Add any complex validation here"""
        super().clean()
        if self.hourly_rate <= 0:
            raise ValidationError("Hourly rate must be positive")
        if self.capacity <= 0:
            raise ValidationError("Capacity must be positive")


class Course(models.Model):
    CATEGORY_CHOICES = (
        ('course', 'course'),
        ('workshop', 'Workshop')
    )
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Must be at least 0.01"
    )
    duration = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Duration in hours (must be at least 1)"
    )
    max_students = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Must be at least 1"
    )
    certification_eligible = models.BooleanField(default=False)
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='courses')
    course_type = models.ForeignKey(CourseType, on_delete=models.CASCADE, related_name='courses')
    
    def __str__(self):
        return self.title
        
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['title', 'department'],
                name='unique_course_title_per_department'
            )
        ]
        
    def clean(self):
        """Model-level validation"""
        super().clean()
        
        if self.duration < 1:
            raise ValidationError("Duration must be at least 1 hour")
            
        if self.price <= 0:
            raise ValidationError("Price must be positive")
            
        if self.max_students <= 0:
            raise ValidationError('Max students must be positive')
            
        if self.course_type.department != self.department:
            raise ValidationError(
                "The selected course type does not belong to the specified department"
            )
    
    @classmethod
    def get_recommended_courses(cls, user, limit=10):
        """Get course recommendations based on user interests and study field with diversification"""
        from core.models import ProfileInterest
        
        # Get user's interests with intensity and study field
        try:
            profile = user.profile
            user_interests = ProfileInterest.objects.filter(profile=profile).select_related('interest')
            user_study_field = profile.studyfield_id
        except:
            return cls.objects.none()
        
        # Build interest scoring dictionary
        interest_scores = {pi.interest_id: pi.intensity for pi in user_interests}
        interest_count = len(interest_scores)
        
        # Find course types that match user interests or study field
        matching_tags = CourseTypeTag.objects.filter(
            models.Q(interest_id__in=interest_scores.keys()) | 
            models.Q(study_field=user_study_field)
        ).values_list('course_type_id', flat=True).distinct()
        
        # Get courses with matching course types, exclude already enrolled
        enrolled_course_ids = set(user.enrollments.values_list('course_id', flat=True))
        
        # Define time window for valid schedule slots (next 3 months)
        today = date.today()
        future_date = today + timedelta(days=90)  # 3 months from now
        
        # Get all matching courses with scoring and valid schedule slots
        courses_with_scores = cls.objects.filter(
            course_type_id__in=matching_tags
        ).exclude(
            id__in=enrolled_course_ids
        ).filter(
            # Only include courses with valid schedule slots
            schedule_slots__valid_from__gte=today,
            schedule_slots__valid_from__lte=future_date
        ).select_related(
            'course_type', 'department'
        ).prefetch_related(
            'wishlists', 'schedule_slots'
        ).annotate(
            # Calculate weighted score based on interest intensity
            match_score=models.Sum(
                models.Case(
                    models.When(
                        course_type__tags__interest_id__in=interest_scores.keys(),
                        then=models.F('course_type__tags__interest_id')
                    ),
                    default=0
                ),
                output_field=models.IntegerField()
            )
        ).annotate(
            # Convert interest IDs to actual intensity scores
            weighted_score=models.Sum(
                models.Case(
                    *[models.When(
                        course_type__tags__interest_id=interest_id,
                        then=intensity
                    ) for interest_id, intensity in interest_scores.items()],
                    default=0
                ),
                output_field=models.IntegerField()
            )
        ).annotate(
            # Add bonus for study field match
            study_field_bonus=models.Case(
                models.When(
                    course_type__tags__study_field=user_study_field,
                    then=3  # Bonus points for study field match
                ),
                default=0
            )
        ).annotate(
            # Final score combines weighted interests + study field bonus
            final_score=models.F('weighted_score') + models.F('study_field_bonus')
        ).order_by('-final_score', 'title')
        
        # Implement diversification algorithm with interest count awareness
        return cls._diversify_recommendations(courses_with_scores, limit, interest_count)
    
    @classmethod
    def _diversify_recommendations(cls, courses_with_scores, limit, interest_count):
        """Diversify recommendations by limiting courses per course type based on scoring and interest count"""
        # Group courses by course type and their scores
        course_type_groups = {}
        for course in courses_with_scores:
            course_type_id = course.course_type.id
            if course_type_id not in course_type_groups:
                course_type_groups[course_type_id] = {
                    'courses': [],
                    'max_score': 0,
                    'course_type_name': course.course_type.name
                }
            course_type_groups[course_type_id]['courses'].append(course)
            course_type_groups[course_type_id]['max_score'] = max(
                course_type_groups[course_type_id]['max_score'], 
                course.final_score
            )
        
        # Sort course types by their maximum score
        sorted_course_types = sorted(
            course_type_groups.items(), 
            key=lambda x: x[1]['max_score'], 
            reverse=True
        )
        
        # Calculate diversification limits based on interest count
        # More interests = more diverse recommendations
        if interest_count >= 8:
            # High interest diversity: More courses per type, more types
            limits = [4, 3, 3, 2, 2, 1, 1, 1]  # Up to 8 course types
        elif interest_count >= 5:
            # Medium interest diversity: Balanced approach
            limits = [3, 2, 2, 1, 1, 1]  # Up to 6 course types
        elif interest_count >= 3:
            # Low-medium interest diversity: Focus on top types
            limits = [3, 2, 1, 1]  # Up to 4 course types
        else:
            # Low interest diversity: Focus on best matches
            limits = [3, 1, 1]  # Up to 3 course types
        
        recommended_courses = []
        
        for i, (course_type_id, group_data) in enumerate(sorted_course_types):
            # Get the limit for this position, or default to 1 if beyond our limits array
            max_courses = limits[i] if i < len(limits) else 1
            max_courses = min(max_courses, len(group_data['courses']))
            
            # Take the top courses from this course type
            courses_to_add = group_data['courses'][:max_courses]
            recommended_courses.extend(courses_to_add)
            
            # Stop if we've reached the limit
            if len(recommended_courses) >= limit:
                break
        
        # Return the diversified list, limited to the requested amount
        return recommended_courses[:limit]

class ScheduleSlot(models.Model):
    DAY_CHOICES = (
        ('mon', 'Monday'),
        ('tue', 'Tuesday'),
        ('wed', 'Wednesday'),
        ('thu', 'Thursday'),
        ('fri', 'Friday'),
        ('sat', 'Saturday'),
        ('sun', 'Sunday')
    )
    
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='schedule_slots')
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE, related_name='schedule_slots')
    teacher = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='teaching_slots',
        limit_choices_to={'user_type': 'teacher'}
    )
    days_of_week = models.JSONField(default=list)
    start_time = models.TimeField()
    end_time = models.TimeField()
    recurring = models.BooleanField(default=True)
    valid_from = models.DateField()
    valid_until = models.DateField(null=True, blank=True)
    
    def __str__(self):
        days = ", ".join([self.get_day_display(day) for day in self.days_of_week])
        teacher_name = self.teacher.get_full_name() if self.teacher else "No teacher"
        return f"{self.course.title} - {teacher_name} - {days} ({self.start_time}-{self.end_time})"
    
    def get_day_display(self, day_code):
        return dict(self.DAY_CHOICES).get(day_code, day_code)
        
    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valid_until__gte=models.F('valid_from')) | 
                     models.Q(valid_until__isnull=True),
                name='valid_until_after_valid_from'
            )
        ]
        
    def clean(self):
        """Model-level validation that works with Django admin"""
        super().clean()
        
        # Basic validations
        if self.valid_from and self.valid_from < date.today() and not self.pk:
            raise ValidationError("Cannot schedule in the past")
            
        if self.valid_until and self.valid_from and self.valid_until < self.valid_from:
            raise ValidationError("End date must be after start date")
            
        if self.recurring and not self.valid_until:
            raise ValidationError("Recurring slots require an end date")
            
        if not self.recurring and self.days_of_week and len(self.days_of_week) > 1:
            raise ValidationError("Non-recurring slots can only have one day specified")

        # Duration validation
        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                raise ValidationError("End time must be after start time")
                
            duration = (self.end_time.hour - self.start_time.hour) + \
                      (self.end_time.minute - self.start_time.minute)/60
            if duration > 8:
                raise ValidationError("Time slots cannot exceed 8 hours")
            if duration < 0.5:
                raise ValidationError("Time slots must be at least 30 minutes")

        # Course capacity vs hall capacity
        if self.course and self.hall and self.course.max_students > self.hall.capacity:
            raise ValidationError(
                f"Course capacity ({self.course.max_students}) "
                f"exceeds hall capacity ({self.hall.capacity})"
            )

        # Date range validation
        if self.valid_from and self.valid_until and (self.valid_until - self.valid_from).days > 365:
            raise ValidationError("Schedule slots cannot span more than 1 year")

        # Hall overlap detection
        if self.hall and self.days_of_week and self.start_time and self.end_time:
            self._check_hall_availability()

        # Teacher availability check
        if self.teacher and self.days_of_week and self.start_time and self.end_time:
            self._check_teacher_availability()

    def _check_hall_availability(self):
        """Check if hall is already booked for the given time slot"""
        # Build day overlap condition
        day_overlap_condition = Q()
        for day in self.days_of_week:
            day_overlap_condition |= Q(days_of_week__contains=[day])
        
        overlap_qs = ScheduleSlot.objects.filter(
            hall=self.hall,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time
        ).filter(day_overlap_condition)
        
        # Date range filtering
        if self.valid_from and self.valid_until:
            overlap_qs = overlap_qs.filter(
                Q(
                    Q(valid_until__isnull=True) & Q(valid_from__lte=self.valid_until)
                ) | Q(
                    Q(valid_until__isnull=False) & 
                    Q(valid_from__lte=self.valid_until) & 
                    Q(valid_until__gte=self.valid_from)
                )
            )
        elif self.valid_from:
            overlap_qs = overlap_qs.filter(
                Q(valid_until__gte=self.valid_from) | Q(valid_until__isnull=True)
            )
        
        # Exclude current instance when updating
        if self.pk:
            overlap_qs = overlap_qs.exclude(pk=self.pk)
        
        if overlap_qs.exists():
            conflicting_slot = overlap_qs.first()
            raise ValidationError(
                f"Hall '{self.hall.name}' is already booked for "
                f"{conflicting_slot.course.title} on {', '.join(conflicting_slot.days_of_week)} "
                f"from {conflicting_slot.start_time} to {conflicting_slot.end_time}"
            )

    def _check_teacher_availability(self):
        """Check if teacher is already booked for the given time slot"""
        # Build day overlap condition
        day_overlap_condition = Q()
        for day in self.days_of_week:
            day_overlap_condition |= Q(days_of_week__contains=[day])
        
        overlap_qs = ScheduleSlot.objects.filter(
            teacher=self.teacher,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time
        ).filter(day_overlap_condition)
        
        # Date range filtering
        if self.valid_from and self.valid_until:
            overlap_qs = overlap_qs.filter(
                Q(
                    Q(valid_until__isnull=True) & Q(valid_from__lte=self.valid_until)
                ) | Q(
                    Q(valid_until__isnull=False) & 
                    Q(valid_from__lte=self.valid_until) & 
                    Q(valid_until__gte=self.valid_from)
                )
            )
        elif self.valid_from:
            overlap_qs = overlap_qs.filter(
                Q(valid_until__gte=self.valid_from) | Q(valid_until__isnull=True)
            )
        
        # Exclude current instance when updating
        if self.pk:
            overlap_qs = overlap_qs.exclude(pk=self.pk)
        
        if overlap_qs.exists():
            conflicting_slot = overlap_qs.first()
            raise ValidationError(
                f"Teacher '{self.teacher.get_full_name()}' is already scheduled for "
                f"{conflicting_slot.course.title} on {', '.join(conflicting_slot.days_of_week)} "
                f"from {conflicting_slot.start_time} to {conflicting_slot.end_time}"
            )

class Booking(models.Model):
    PURPOSE_CHOICES = (
        ('course', 'Course'),
        ('tutoring', 'Tutoring'),
        ('meeting', 'Meeting'),
        ('event', 'Event'),
        ('other', 'Other')
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('cancelled', 'Cancelled')
    )
    
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE, related_name='bookings')
    purpose = models.CharField(max_length=10, choices=PURPOSE_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings_requested')
    student = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                               related_name='bookings_as_student', limit_choices_to={'user_type': 'student'})
    tutor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='bookings_as_tutor', limit_choices_to={'user_type': 'teacher'})
    # Guest information fields
    guest_name = models.CharField(max_length=255, null=True, blank=True)
    guest_email = models.EmailField(null=True, blank=True)
    guest_phone = models.CharField(max_length=20, null=True, blank=True)
    guest_organization = models.CharField(max_length=255, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.get_purpose_display()} - {self.hall.name} ({self.start_datetime})"
    
    class Meta:
        ordering = ['-start_datetime']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(start_datetime__lt=models.F('end_datetime')),
                name='booking_start_before_end'
            ),
        ]

class Wishlist(models.Model):
    owner = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='wishlist'
    )
    courses = models.ManyToManyField(
        'Course',
        related_name='wishlists',
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Wishlists"

    def __str__(self):
        return f"Wishlist of {self.owner.phone}"

class Enrollment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    )
    
    PAYMENT_STATUS_CHOICES = (
        ('partial', 'Partial'),
        ('paid', 'Paid'),
        ('refunded', 'Refunded')
    )
    PAYMENT_METHOD_CHOICES = (
        ('ewallet', 'eWallet'),
        ('cash', 'Cash'),
    )
    
    payment_method = models.CharField(
        max_length=10,
        choices=PAYMENT_METHOD_CHOICES,
        null=True,
        blank=True
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='enrollments'
    )
    # Add these new fields
    first_name = models.CharField(max_length=150, blank=True)
    middle_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(
        max_length=20,
        blank=True,
        validators=[syrian_phone_validator]
    )
    is_guest = models.BooleanField(default=False)
    enrolled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_enrollments',
        limit_choices_to={'user_type': 'reception'}
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    schedule_slot = models.ForeignKey(
        ScheduleSlot,
        on_delete=models.SET_NULL,
        null=True,
        related_name='enrollments'
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending'
    )
    payment_status = models.CharField(
        max_length=10,
        choices=PAYMENT_STATUS_CHOICES,
        default='partial'
    )
    enrollment_date = models.DateTimeField(auto_now_add=True)
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-enrollment_date']
        
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.course.title}"
    
    def clean(self):
        """Model-level validation"""
        super().clean()
        
        # Check if student is already enrolled
        if not self.pk:  # Only check on creation
            if Enrollment.objects.filter(
                student=self.student,
                course=self.course,
                status__in=['pending', 'active']
            ).exists():
                raise ValidationError("Student is already enrolled in this course")
        
        # Check schedule slot capacity
        if self.schedule_slot:
            if self.schedule_slot.course != self.course:
                raise ValidationError("Schedule slot does not belong to the selected course")
            
            # Count active enrollments for this schedule slot
            active_enrollments = Enrollment.objects.filter(
                schedule_slot=self.schedule_slot,
                status__in=['pending', 'active']
            ).exclude(pk=self.pk).count()
            
            if active_enrollments >= self.course.max_students:
                raise ValidationError("Schedule slot has reached maximum capacity")
    
    def update_status(self):
        """Update status based on schedule slot dates"""
        if not self.schedule_slot:
            return
            
        today = date.today()
        
        if self.status != 'cancelled':
            if today < self.schedule_slot.valid_from:
                self.status = 'pending'
            elif today >= self.schedule_slot.valid_from and (
                not self.schedule_slot.valid_until or 
                today <= self.schedule_slot.valid_until
            ):
                self.status = 'active'
            elif self.schedule_slot.valid_until and today > self.schedule_slot.valid_until:
                self.status = 'completed'
    
    def process_payment(self, amount, payment_method='ewallet'):
        """Process payment with support for both eWallet and cash"""
        from core.models import EWallet, Transaction
        
        amount = amount.quantize(Decimal('0.00'))
        if amount <= 0:
            raise ValidationError("Payment amount must be positive")
            
        if amount > self.course.price - self.amount_paid:
            raise ValidationError("Payment amount exceeds remaining balance")
        
        # Set payment method automatically
        self.payment_method = payment_method
        
        if payment_method == 'ewallet':
            if not self.student:
                raise ValidationError("eWallet payments require a registered student")
                
            try:
                student_wallet = EWallet.objects.get(user=self.student)
                admin = User.objects.get(is_staff=True)
                admin_wallet = EWallet.objects.get(user=admin)
                
                if student_wallet.current_balance < amount:
                    raise ValidationError("Insufficient wallet balance")
                    
                student_wallet.current_balance -= amount
                admin_wallet.current_balance += amount
                student_wallet.save()
                admin_wallet.save()
                
                Transaction.objects.create(
                    sender=self.student,
                    receiver=admin,
                    amount=amount,
                    transaction_type='course_payment',
                    status='completed',
                    description=f"eWallet payment for course: {self.course.title}",
                    reference_id=f"ENR-{self.id}-{int(time.time())}"
                )
                
            except (EWallet.DoesNotExist, User.DoesNotExist) as e:
                raise ValidationError(f"Failed to process eWallet payment: {str(e)}")
            except Exception as e:
                raise ValidationError(f"Unexpected error during eWallet payment: {str(e)}")
                
        elif payment_method == 'cash':
            try:
                admin = User.objects.filter(is_staff=True).first()
                if not admin:
                    raise ValidationError("Admin account not found")
                admin_wallet = EWallet.objects.get(user=admin)
                admin_wallet.deposit(amount)

                # Get or create a generic Guest user
                guest_user, _ = User.objects.get_or_create(
                    phone='guest',
                    defaults={
                        'first_name': 'Guest',
                        'middle_name': 'Guest',
                        'last_name': 'User',
                        'user_type': 'student',
                        'is_active': False
                    }
                )

                Transaction.objects.create(
                    sender=guest_user,
                    receiver=admin,
                    amount=amount,
                    transaction_type='course_payment',
                    status='completed',
                    description=(
                        f"Cash payment from {self.first_name} {self.last_name} "
                        f"(Phone: {self.phone}) - Course: {self.course.title}"
                    ),
                    reference_id=f"CASH-{self.id}-{int(time.time())}",
                )

            except Exception as e:
                raise ValidationError(f"Failed to process cash payment: {str(e)}")
            
        # Update enrollment status
        self.amount_paid += amount
        self.payment_status = 'paid' if self.amount_paid >= self.course.price else 'partial'
        self.save()

    def cancel(self):
        """Cancel enrollment and process refund"""
        if self.status == 'cancelled':
            return
            
        # Process refund if payment was made
        if self.amount_paid > 0:
            from core.models import EWallet, Transaction
            
            try:
                admin = User.objects.get(is_staff=True)
                admin_wallet = EWallet.objects.get(user=admin)
                
                # For guest enrollments, we just deduct from admin wallet
                if self.is_guest:
                    # Use the generic Guest user as receiver
                    guest_user, _ = User.objects.get_or_create(
                        phone='guest',
                        defaults={
                            'first_name': 'Guest',
                            'middle_name': 'Guest',
                            'last_name': 'User',
                            'user_type': 'student',
                            'is_active': False
                        }
                    )
                    admin_wallet.withdraw(self.amount_paid)
                    
                    Transaction.objects.create(
                        sender=admin,
                        receiver=guest_user,  # Use guest user as receiver
                        amount=self.amount_paid,
                        transaction_type='course_refund',
                        status='completed',
                        description=(
                            f"Cash refund for {self.first_name} {self.last_name} "
                            f"(Phone: {self.phone}) - Course: {self.course.title}"
                        ),
                        reference_id=f"REFUND-{self.id}-{int(time.time())}"
                    )
                else:
                    # Regular student refund
                    student_wallet = EWallet.objects.get(user=self.student)
                    
                    if admin_wallet.current_balance < self.amount_paid:
                        raise ValidationError("Insufficient admin wallet balance for refund")
                    
                    student_wallet.current_balance += self.amount_paid
                    admin_wallet.current_balance -= self.amount_paid
                    student_wallet.save()
                    admin_wallet.save()
                    
                    Transaction.objects.create(
                        sender=admin,
                        receiver=self.student,
                        amount=self.amount_paid,
                        transaction_type='course_refund',
                        status='completed',
                        description=f"Refund for cancelled course: {self.course.title}",
                        reference_id=f"ENR-{self.id}-REF"
                    )
                
            except (EWallet.DoesNotExist, User.DoesNotExist):
                raise ValidationError("Required wallets not found for refund")
            
        self.status = 'cancelled'
        self.payment_status = 'refunded'
        self.save()
    
    def save(self, *args, **kwargs):
        self.full_clean()
        self.update_status()  # Update status before saving
        super().save(*args, **kwargs)
        
class Lesson(models.Model):
    """
    Model for lessons within courses
    """
    title = models.CharField(max_length=200)
    notes = models.TextField(blank=True, null=True, help_text="Lesson notes and content")
    file = models.FileField(
        upload_to='lessons/files/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt', 'zip'])],
        help_text="Upload lesson materials (PDF, DOC, PPT, etc.)"
    )
    link = models.URLField(blank=True, null=True, help_text="External link for lesson resources")
    
    # Relationships
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='lessons')
    schedule_slot = models.ForeignKey('ScheduleSlot', on_delete=models.CASCADE, related_name='lessons')
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_lessons')
    
    # Metadata
    lesson_order = models.PositiveIntegerField(default=1, help_text="Order of lesson in the course")
    lesson_date = models.DateField(help_text="Date when lesson is scheduled/conducted")
    #duration_minutes = models.PositiveIntegerField(default=60, help_text="Lesson duration in minutes")
    
    # Status
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Completed')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['lesson_date', 'lesson_order']
        unique_together = ['course', 'lesson_order']
    
    def __str__(self):
        return f"{self.course.title} - Lesson {self.lesson_order}: {self.title}"
    
    @property
    def file_name(self):
        """Get the filename without path"""
        if self.file:
            return os.path.basename(self.file.name)
        return None
    
    @property
    def file_size(self):
        """Get file size in bytes"""
        if self.file:
            return self.file.size
        return None

    @property
    def duration_hours(self):
        """Calculate duration in hours from schedule slot times"""
        if self.schedule_slot and self.schedule_slot.start_time and self.schedule_slot.end_time:
            # Create datetime objects for calculation
            start_dt = datetime.combine(date.today(), self.schedule_slot.start_time)
            end_dt = datetime.combine(date.today(), self.schedule_slot.end_time)
            
            # Calculate duration
            duration = end_dt - start_dt
            return round(duration.total_seconds() / 3600, 2)  # Convert seconds to hours
        return 0.0
class Homework(models.Model):
    """
    Model for homework assignments for lessons
    """
    title = models.CharField(max_length=200)
    description = models.TextField(help_text="Homework description and instructions")
    form_link = models.URLField(
        blank=True, 
        null=True, 
        help_text="Link to Google Form, survey, or submission form"
    )
    deadline = models.DateTimeField(help_text="Homework submission deadline")
    
    # Relationships
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='homework_assignments')
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='homework_assignments')
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assigned_homework')
    
    # Additional fields
    max_score = models.PositiveIntegerField(default=100, help_text="Maximum possible score")
    is_mandatory = models.BooleanField(default=True, help_text="Whether homework is mandatory")
    
    # Status
    STATUS_CHOICES = [
        ('published', 'Published'),
        ('closed', 'Closed'),
    ]
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='published',  # Change default to published
        editable=False  # Make non-editable through forms/API
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.lesson.title} - {self.title}"
    
    @property
    def is_overdue(self):
        """Check if homework deadline has passed"""
        from django.utils import timezone
        return timezone.now() > self.deadline
    
    @property
    def days_until_deadline(self):
        """Get days until deadline"""
        from django.utils import timezone
        if self.is_overdue:
            return 0
        delta = self.deadline - timezone.now()
        return delta.days
class Attendance(models.Model):
    """
    Model for tracking student attendance in lessons
    """
    ATTENDANCE_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
    ]
    
    # Relationships
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance_records')
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='attendance_records')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='attendance_records')
    teacher = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='recorded_attendance',
        help_text="Teacher who recorded the attendance"
    )
    
    # Attendance data
    attendance = models.CharField(max_length=20, choices=ATTENDANCE_CHOICES)
    notes = models.TextField(blank=True, null=True, help_text="Additional notes about attendance")
    
    # Timestamps
    recorded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['student', 'lesson']
        ordering = ['-recorded_at']
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.lesson.title} - {self.get_attendance_display()}"
