from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import generic
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User

from .models import Course, Enrollment, Question, Choice, Submission

import logging

logger = logging.getLogger(__name__)


def registration_request(request):
    context = {}

    if request.method == "GET":
        return render(
            request,
            "onlinecourse/user_registration_bootstrap.html",
            context,
        )

    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["psw"]
        first_name = request.POST["firstname"]
        last_name = request.POST["lastname"]

        try:
            User.objects.get(username=username)
            user_exist = True
        except User.DoesNotExist:
            user_exist = False

        if not user_exist:
            user = User.objects.create_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                password=password,
            )
            login(request, user)
            return redirect("onlinecourse:index")

        context["message"] = "User already exists."
        return render(
            request,
            "onlinecourse/user_registration_bootstrap.html",
            context,
        )


def login_request(request):
    context = {}

    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["psw"]

        user = authenticate(username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("onlinecourse:index")

        context["message"] = "Invalid username or password."
        return render(
            request,
            "onlinecourse/user_login_bootstrap.html",
            context,
        )

    return render(
        request,
        "onlinecourse/user_login_bootstrap.html",
        context,
    )


def logout_request(request):
    logout(request)
    return redirect("onlinecourse:index")


def check_if_enrolled(user, course):
    if not user.is_authenticated:
        return False

    return Enrollment.objects.filter(
        user=user,
        course=course,
    ).exists()


class CourseListView(generic.ListView):
    template_name = "onlinecourse/course_list_bootstrap.html"
    context_object_name = "course_list"

    def get_queryset(self):
        user = self.request.user
        courses = Course.objects.order_by("-total_enrollment")[:10]

        for course in courses:
            if user.is_authenticated:
                course.is_enrolled = check_if_enrolled(user, course)

        return courses


class CourseDetailView(generic.DetailView):
    model = Course

    # Use the template name required by the assignment.
    template_name = "onlinecourse/course_details_bootstrap.html"


def enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    user = request.user

    is_enrolled = check_if_enrolled(user, course)

    if not is_enrolled and user.is_authenticated:
        Enrollment.objects.create(
            user=user,
            course=course,
            mode="honor",
        )

        course.total_enrollment += 1
        course.save()

    return HttpResponseRedirect(
        reverse(
            viewname="onlinecourse:course_details",
            args=(course.id,),
        )
    )


def extract_answers(request):
    submitted_answers = []

    for key in request.POST:
        if key.startswith("choice"):
            value = request.POST[key]

            try:
                choice_id = int(value)
            except (TypeError, ValueError):
                continue

            submitted_answers.append(choice_id)

    return submitted_answers


def submit(request, course_id):
    """Save exam answers and redirect to the exam result."""
    course = get_object_or_404(Course, pk=course_id)

    if not request.user.is_authenticated:
        return redirect("onlinecourse:login")

    enrollment = get_object_or_404(
        Enrollment,
        user=request.user,
        course=course,
    )

    submission = Submission.objects.create(
        enrollment=enrollment,
    )

    selected_ids = extract_answers(request)

    for choice_id in selected_ids:
        choice = get_object_or_404(
            Choice,
            pk=choice_id,
            question__course=course,
        )
        submission.choices.add(choice)

    return HttpResponseRedirect(
        reverse(
            "onlinecourse:show_exam_result",
            args=(course.id, submission.id),
        )
    )


def show_exam_result(request, course_id, submission_id):
    """Calculate the exam score and render the result page."""
    course = get_object_or_404(Course, pk=course_id)

    submission = get_object_or_404(
        Submission,
        pk=submission_id,
        enrollment__course=course,
    )

    selected_ids = list(
        submission.choices.values_list("id", flat=True)
    )

    questions = list(course.question_set.all())

    grade = 0
    possible = 0

    for question in questions:
        possible += question.grade

        if question.is_get_score(selected_ids):
            grade += question.grade

    context = {
        "course": course,
        "grade": grade,
        "possible": possible,
        "possible_score": possible,
        "questions": questions,
        "selected_ids": selected_ids,
        "choices": submission.choices.all(),
        "submission": submission,
    }

    return render(
        request,
        "onlinecourse/exam_result_bootstrap.html",
        context,
    )
