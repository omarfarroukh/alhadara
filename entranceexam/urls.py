from rest_framework.routers import DefaultRouter
from .views import (
    LanguageViewSet,
    LanguageLevelViewSet,
    QuestionBankViewSet,
    EntranceExamViewSet,
    ExamAttemptViewSet,
)

router = DefaultRouter()
router.register('languages', LanguageViewSet)
router.register('levels', LanguageLevelViewSet)
router.register('questionbanks', QuestionBankViewSet)
router.register('exams', EntranceExamViewSet)
router.register('attempts', ExamAttemptViewSet, basename='attempt')   # ← add basename
urlpatterns = router.urls