from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

from .views import (
    LanguageViewSet, LanguageLevelViewSet, EntranceExamViewSet,
    ExamQuestionViewSet, ExamAttemptViewSet, ExamAnswerViewSet
)

# Create the main router
router = DefaultRouter()
router.register(r'languages', LanguageViewSet, basename='language')
router.register(r'language-levels', LanguageLevelViewSet, basename='languagelevel')
router.register(r'exams', EntranceExamViewSet, basename='entranceexam')
router.register(r'attempts', ExamAttemptViewSet, basename='examattempt')

# Create nested routers for questions under exams
exams_router = routers.NestedSimpleRouter(router, r'exams', lookup='exam')
exams_router.register(r'questions', ExamQuestionViewSet, basename='exam-questions')

# Create nested routers for answers under attempts
attempts_router = routers.NestedSimpleRouter(router, r'attempts', lookup='attempt')
attempts_router.register(r'answers', ExamAnswerViewSet, basename='attempt-answers')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(exams_router.urls)),
    path('', include(attempts_router.urls)),
] 