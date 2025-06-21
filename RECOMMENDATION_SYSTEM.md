# Course Recommendation System

A smart course recommendation system that matches students with courses based on their interests and study fields using a hashtag-like tagging system with intensity-based scoring, intelligent diversification, and schedule-aware filtering.

## 🚀 Features

- **Interest-based matching**: Courses are recommended based on student interests
- **Intensity-weighted scoring**: Interest intensity (1-5) affects recommendation ranking
- **Study field matching**: Recommendations also consider academic background with bonus points
- **Smart scoring**: Courses are ranked by weighted relevance score
- **Intelligent diversification**: Limits courses per course type to ensure variety
- **Interest count awareness**: Users with more interests get more diverse recommendations
- **Schedule slot validation**: Only recommends courses with upcoming/available schedule slots
- **Exclusion logic**: Already enrolled courses are automatically excluded
- **Easy tagging**: Simple API to add/remove tags from course types

## 🏗️ Architecture

### Core Components

1. **CourseTypeTag Model**: Links interests and study fields to course types
2. **Course.get_recommended_courses()**: Main recommendation algorithm with intensity scoring
3. **Course._diversify_recommendations()**: Diversification algorithm with interest count awareness
4. **Schedule slot filtering**: Ensures only courses with valid upcoming slots are recommended
5. **CourseType tagging methods**: Easy tag management
6. **API endpoints**: RESTful endpoints for recommendations and tag management

### How It Works

1. Students add interests to their profile with intensity levels (1-5)
2. Course types are tagged with relevant interests and study fields
3. The system finds courses whose course types match student interests/study fields
4. **Schedule validation**: Only includes courses with schedule slots starting within next 3 months
5. **Intensity-based scoring**: Each matching interest contributes its intensity value to the score
6. **Study field bonus**: +3 points for courses matching the student's study field
7. **Interest count awareness**: Diversification limits based on number of user interests:
   - 8+ interests: High diversity (4, 3, 3, 2, 2, 1, 1, 1)
   - 5-7 interests: Medium diversity (3, 2, 2, 1, 1, 1)
   - 3-4 interests: Low-medium diversity (3, 2, 1, 1)
   - 1-2 interests: Low diversity (3, 1, 1)
8. Results are ranked by final score within each course type
9. Already enrolled courses are excluded

## 📡 API Endpoints

### Get Recommendations
```
GET /api/courses/recommendations/?limit=10
```
Returns personalized course recommendations for the authenticated student, ranked by intensity-weighted scoring with intelligent diversification and schedule validation.

### Manage Course Type Tags
```
POST /api/course-types/{id}/add_tag/
{
    "interest_id": 1,
    "study_field_id": 2
}

POST /api/course-types/{id}/remove_tag/
{
    "interest_id": 1,
    "study_field_id": 2
}

GET /api/course-types/{id}/tags/
```

## 🛠️ Usage Examples

### Python/Django Shell
```python
# Get recommendations for a student
student = User.objects.get(phone='0999999999')
recommendations = Course.get_recommended_courses(student, limit=8)

# Add tags to a course type
course_type = CourseType.objects.get(name='Web Development')
interest = Interest.objects.get(name='Programming')
course_type.add_interest_tag(interest)

# Get all tags for a course type
tags = course_type.get_tags()
print(tags)  # {'interests': ['Programming', 'Web Development'], 'study_fields': ['Computer Science']}
```

### API Usage
```bash
# Get recommendations
curl -H "Authorization: Bearer YOUR_TOKEN" \
     "http://localhost:8000/api/courses/recommendations/?limit=8"

# Add interest tag to course type
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"interest_id": 1}' \
     "http://localhost:8000/api/course-types/1/add_tag/"
```

## 🧪 Testing

Run the test script to see the system in action:
```bash
python test_recommendations.py
```

## 🗄️ Database Setup

1. Run migrations:
```bash
python manage.py makemigrations
python manage.py migrate
```

2. Seed sample data:
```bash
python manage.py seed_data
```

3. Seed course type tags:
```bash
python manage.py seed_course_tags
```

4. Add schedule slots (for testing):
```bash
python add_schedule_slots.py
```

## 🎯 Algorithm Details

The recommendation algorithm with intensity scoring, diversification, and schedule validation:

1. **Gathers user data**: Extracts interests with intensity levels and study field from user profile
2. **Finds matching tags**: Queries CourseTypeTag for matching interests/study fields
3. **Filters courses**: Gets courses with matching course types
4. **Validates schedule slots**: Only includes courses with slots starting within next 3 months
5. **Excludes enrolled**: Removes courses the student is already enrolled in
6. **Calculates weighted score**: Sums intensity values for each matching interest
7. **Adds study field bonus**: +3 points for courses matching student's study field
8. **Computes final score**: `final_score = weighted_score + study_field_bonus`
9. **Groups by course type**: Organizes courses by their course type
10. **Applies interest-aware diversification**:
    - 8+ interests: [4, 3, 3, 2, 2, 1, 1, 1] courses per type
    - 5-7 interests: [3, 2, 2, 1, 1, 1] courses per type
    - 3-4 interests: [3, 2, 1, 1] courses per type
    - 1-2 interests: [3, 1, 1] courses per type
11. **Returns diversified list**: Courses from multiple course types, ranked by score

### Scoring Example
```
Student interests (6 total):
- Programming (intensity: 5)
- Web Development (intensity: 4)
- Mathematics (intensity: 3)
- Design (intensity: 2)
- Business (intensity: 4)
- Marketing (intensity: 3)
Study field: Computer Science

Course Type Rankings:
1. Web Development (score: 11) → Max 3 courses (medium diversity)
2. Data Science (score: 8) → Max 2 courses
3. Programming Languages (score: 8) → Max 2 courses
4. Business Management (score: 7) → Max 1 course
5. Mobile Development (score: 5) → Max 1 course

Result: 3 Web Dev + 2 Data Science + 2 Programming + 1 Business + 1 Mobile = 9 courses total
```

## 🔧 Customization

### Adding New Interest Categories
```python
# In core/models.py, add to Interest.CATEGORY_CHOICES
CATEGORY_CHOICES = (
    ('academic', 'Academic'),
    ('hobby', 'Hobby'),
    ('professional', 'Professional'),
    ('sports', 'Sports'),  # New category
)
```

### Modifying Scoring Weights
```python
# In courses/models.py, modify the study_field_bonus value
study_field_bonus=models.Case(
    models.When(
        course_type__tags__study_field=user_study_field,
        then=5  # Change from 3 to 5 for higher study field weight
    ),
    default=0
)
```

### Modifying Schedule Validation Window
```python
# In courses/models.py, modify the time window
future_date = today + timedelta(days=180)  # Change from 90 to 180 days
```

### Modifying Interest Count Diversification
```python
# In courses/models.py, modify the _diversify_recommendations method
if interest_count >= 10:  # Change from 8 to 10
    limits = [5, 4, 3, 3, 2, 2, 1, 1, 1, 1]  # More diverse for high interest counts
```

### Modifying Recommendation Logic
Override the `get_recommended_courses` method in the Course model to implement custom scoring algorithms.

## 📊 Performance

- Uses efficient database queries with select_related and prefetch_related
- Implements proper indexing on foreign keys
- Caches user interests and study field for faster lookups
- Limits results to prevent performance issues
- Uses database-level aggregation for scoring calculations
- Diversification happens in Python for flexibility
- Schedule validation uses database filtering for efficiency

## 🔒 Security

- All endpoints require authentication
- Students can only see their own recommendations
- Tag management restricted to authorized users
- Input validation on all tag operations

## 🎨 Intensity Levels

The system uses a 1-5 intensity scale:
- **1**: Very low interest
- **2**: Low interest
- **3**: Medium interest
- **4**: High interest
- **5**: Very high interest

Higher intensity interests have more weight in the recommendation algorithm, ensuring that courses matching a student's strongest interests appear first in recommendations.

## 🎯 Diversification Benefits

- **Prevents over-representation**: No single course type dominates recommendations
- **Encourages exploration**: Students discover courses from different areas
- **Balanced exposure**: Mix of high-scoring and alternative options
- **Better user experience**: More variety in recommendations
- **Configurable limits**: Easy to adjust diversification rules
- **Interest-aware**: Users with more interests get more diverse recommendations

## 📅 Schedule Validation Benefits

- **Practical recommendations**: Only shows courses that are actually available
- **Time-aware**: Focuses on upcoming courses (next 3 months)
- **User-friendly**: No disappointment from seeing unavailable courses
- **Configurable window**: Easy to adjust the time window (currently 90 days)
- **Database efficient**: Uses database filtering for performance 