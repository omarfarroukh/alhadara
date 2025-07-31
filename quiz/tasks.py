# tasks.py - Improved version
import httpx
import json
import os
import logging
from django.core.files.storage import default_storage
from .models import Quiz, Question, Choice
from .serializers import QuestionCreateSerializer, ChoiceCreateSerializer

logger = logging.getLogger(__name__)

FASTAPI_URL = os.getenv("QUIZGEN_URL", "http://localhost:8080")

def generate_questions_for_quiz(quiz_id: int, file_path: str, num_questions: int, difficulty: str):
    """
    RQ job: download file, hit FastAPI, create questions.
    """
    try:
        # Get the quiz object
        quiz = Quiz.objects.get(pk=quiz_id)
        logger.info(f"Starting question generation for quiz {quiz_id}")
        
        # Read the file and prepare for HTTP request
        with default_storage.open(file_path, "rb") as f:
            file_content = f.read()
            filename = os.path.basename(file_path)
            
            # Prepare the request
            files = {"file": (filename, file_content)}
            data = {"num_questions": num_questions, "difficulty": difficulty}
            
            # Make HTTP request to FastAPI with increased timeout
            logger.info(f"Calling FastAPI at {FASTAPI_URL}/generate-questions")
            response = httpx.post(
                f"{FASTAPI_URL}/generate-questions", 
                files=files, 
                data=data, 
                timeout=500  # Increased timeout for complex processing
            )
            
            # Log response details for debugging
            logger.info(f"FastAPI response status: {response.status_code}")
            if response.status_code != 200:
                logger.error(f"FastAPI error response: {response.text}")
                
            response.raise_for_status()
            
        # Parse the response
        try:
            questions_data = response.json()
            logger.info(f"Received {len(questions_data)} questions from FastAPI")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Raw response: {response.text}")
            raise ValueError(f"Invalid JSON response from FastAPI: {e}")
        
        # Validate questions data structure
        if not isinstance(questions_data, list):
            logger.error(f"Expected list of questions, got: {type(questions_data)}")
            raise ValueError("Invalid response format: expected list of questions")
        
        # Remove duplicates based on question text similarity
        unique_questions = []
        seen_questions = set()
        
        for question_data in questions_data:
            # Validate question structure
            if not isinstance(question_data, dict):
                logger.warning(f"Skipping invalid question data: {question_data}")
                continue
                
            question_text = question_data.get("text", "").lower().strip()
            if not question_text:
                logger.warning(f"Skipping question with empty text: {question_data}")
                continue
                
            # Simple duplicate detection - check if questions are too similar
            is_duplicate = False
            for seen_text in seen_questions:
                # Check if questions are very similar (more than 70% similar words)
                words1 = set(question_text.split())
                words2 = set(seen_text.split())
                if len(words1) > 0 and len(words2) > 0:
                    similarity = len(words1.intersection(words2)) / len(words1.union(words2))
                    if similarity > 0.7:
                        is_duplicate = True
                        logger.info(f"Detected duplicate question: {question_text[:50]}...")
                        break
            
            if not is_duplicate:
                seen_questions.add(question_text)
                unique_questions.append(question_data)
        
        # Limit to requested number of questions
        if len(unique_questions) > num_questions:
            unique_questions = unique_questions[:num_questions]
            logger.info(f"Truncated to {num_questions} unique questions")
        elif len(unique_questions) < num_questions:
            logger.warning(f"Only got {len(unique_questions)} unique questions, requested {num_questions}")
        
        if not unique_questions:
            raise ValueError("No valid questions were generated")
        
        # Create questions and choices in database
        created_questions = []
        
        for idx, question_data in enumerate(unique_questions):
            try:
                # Validate question data
                question_text = question_data.get("text", "").strip()
                question_type = question_data.get("question_type", "multiple_choice")
                choices_data = question_data.get("choices", [])
                
                if not question_text:
                    logger.warning(f"Skipping question {idx + 1} with empty text")
                    continue
                
                if question_type not in ["multiple_choice", "true_false"]:
                    logger.warning(f"Skipping question {idx + 1} with invalid type: {question_type}")
                    continue
                
                if not choices_data or not isinstance(choices_data, list):
                    logger.warning(f"Skipping question {idx + 1} with invalid choices: {choices_data}")
                    continue
                
                # Validate choices based on question type
                if question_type == "multiple_choice" and len(choices_data) != 4:
                    logger.warning(f"Multiple choice question {idx + 1} has {len(choices_data)} choices, expected 4")
                    continue
                elif question_type == "true_false" and len(choices_data) != 2:
                    logger.warning(f"True/false question {idx + 1} has {len(choices_data)} choices, expected 2")
                    continue
                
                # Check for invalid multiple choice questions with True/False answers
                if question_type == "multiple_choice":
                    choice_texts = [c.get("text", "").lower() for c in choices_data if isinstance(c, dict)]
                    if "true" in choice_texts and "false" in choice_texts:
                        logger.warning(f"Skipping invalid multiple choice question {idx + 1} with True/False answers")
                        continue
                
                # Validate that exactly one choice is correct
                correct_choices = [c for c in choices_data if isinstance(c, dict) and c.get("is_correct", False)]
                if len(correct_choices) != 1:
                    logger.warning(f"Question {idx + 1} has {len(correct_choices)} correct choices, expected 1")
                    # Fix by making first choice correct if none are marked
                    if len(correct_choices) == 0 and choices_data:
                        choices_data[0]["is_correct"] = True
                        logger.info(f"Fixed question {idx + 1} by marking first choice as correct")
                    else:
                        continue
                
                # Prepare complete question data with nested choices and correct order
                question_payload = {
                    "quiz": quiz.id,
                    "text": question_text,
                    "question_type": question_type,
                    "order": idx + 1,  # Use loop index for proper sequential ordering
                    "points": 1,
                    "is_required": True,
                    "choices": choices_data
                }
                
                # Create and validate question serializer with nested choices
                question_serializer = QuestionCreateSerializer(data=question_payload)
                if question_serializer.is_valid():
                    # Save the question (this will also create the choices via the nested serializer)
                    question = question_serializer.save()
                    logger.info(f"Created question {question.id} (order {idx + 1}): {question.text[:50]}... with {len(choices_data)} choices")
                    created_questions.append(question)
                else:
                    logger.error(f"Question {idx + 1} validation failed: {question_serializer.errors}")
                    # Don't raise exception, just skip this question
                    continue
                    
            except Exception as e:
                logger.error(f"Error processing question {idx + 1}: {e}")
                continue  # Skip this question and continue with others
        
        # Clean up the temporary file
        try:
            default_storage.delete(file_path)
            logger.info(f"Deleted temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to delete temporary file {file_path}: {e}")
        
        if not created_questions:
            raise ValueError("No questions could be created from the generated data")
        
        result = {
            "quiz_id": quiz.id,
            "questions_created": len(created_questions),
            "question_ids": [q.id for q in created_questions]
        }
        
        logger.info(f"Successfully created {len(created_questions)} questions for quiz {quiz_id}")
        return result
        
    except Quiz.DoesNotExist:
        logger.error(f"Quiz with id {quiz_id} does not exist")
        # Clean up file on error
        try:
            default_storage.delete(file_path)
        except:
            pass
        raise ValueError(f"Quiz with id {quiz_id} does not exist")
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error from FastAPI: {e.response.status_code} - {e.response.text}")
        # Clean up file on error
        try:
            default_storage.delete(file_path)
        except:
            pass
        raise ValueError(f"FastAPI request failed: {e.response.status_code} - {e.response.text}")
        
    except httpx.RequestError as e:
        logger.error(f"Request error: {e}")
        # Clean up file on error
        try:
            default_storage.delete(file_path)
        except:
            pass
        raise ValueError(f"Failed to connect to FastAPI service: {e}")
        
    except Exception as e:
        logger.error(f"Unexpected error in generate_questions_for_quiz: {e}")
        # Clean up file on error
        try:
            default_storage.delete(file_path)
        except:
            pass
        raise