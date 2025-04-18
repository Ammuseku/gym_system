from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from django.http import JsonResponse
from django.urls import reverse
from datetime import timedelta, date
from .models import (
    MuscleGroup, Exercise, WorkoutPlan, PlanExercise,
    UserWorkoutPlan, UserPlanExercise, WorkoutSchedule
)
from .forms import (
    MuscleGroupForm, ExerciseForm, WorkoutPlanForm, PlanExerciseForm,
    PlanExerciseFormSet, UserPlanExerciseForm, WorkoutScheduleForm,
    ExerciseFilterForm, WorkoutPlanFilterForm
)
from progress.models import WorkoutLog


@login_required
def dashboard(request):
    # Get user's active workout plans
    active_plans = UserWorkoutPlan.objects.filter(
        user=request.user,
        is_active=True
    ).select_related('workout_plan')

    # Get upcoming scheduled workouts
    today = timezone.now().date()
    upcoming_workouts = WorkoutSchedule.objects.filter(
        user=request.user,
        date__gte=today,
        completed=False
    ).order_by('date', 'start_time')[:5]

    # Get recent workout logs
    recent_logs = WorkoutLog.objects.filter(
        user=request.user
    ).order_by('-date')[:5]

    # Get workout suggestions based on user profile
    suggested_plans = []
    if hasattr(request.user, 'profile'):
        profile = request.user.profile
        suggested_plans = WorkoutPlan.objects.filter(
            is_public=True,
            goal=profile.primary_goal
        ).exclude(
            users__user=request.user
        ).order_by('-created_at')[:3]

    context = {
        'active_plans': active_plans,
        'upcoming_workouts': upcoming_workouts,
        'recent_logs': recent_logs,
        'suggested_plans': suggested_plans,
    }

    return render(request, 'workouts/dashboard.html', context)


@login_required
def exercise_library(request):
    form = ExerciseFilterForm(request.GET)
    exercises = Exercise.objects.all()

    # Apply filters
    if form.is_valid():
        if form.cleaned_data['search']:
            query = form.cleaned_data['search']
            exercises = exercises.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query)
            )

        if form.cleaned_data['muscle_group']:
            muscle_group = form.cleaned_data['muscle_group']
            exercises = exercises.filter(
                Q(muscle_group=muscle_group) |
                Q(secondary_muscle_groups=muscle_group)
            ).distinct()

        if form.cleaned_data['difficulty']:
            exercises = exercises.filter(difficulty=form.cleaned_data['difficulty'])

        if form.cleaned_data['category']:
            exercises = exercises.filter(category=form.cleaned_data['category'])

        if form.cleaned_data['equipment']:
            equipment = form.cleaned_data['equipment']
            exercises = exercises.filter(equipment_needed__icontains=equipment)

    # Get all muscle groups for sidebar
    muscle_groups = MuscleGroup.objects.annotate(
        exercise_count=Count('exercises')
    ).order_by('name')

    context = {
        'exercises': exercises,
        'muscle_groups': muscle_groups,
        'form': form,
    }

    return render(request, 'workouts/exercise_library.html', context)


@login_required
def exercise_detail(request, pk):
    exercise = get_object_or_404(Exercise, pk=pk)

    # Get user's exercise logs for this exercise
    logs = UserPlanExercise.objects.filter(
        user=request.user,
        plan_exercise__exercise=exercise
    ).order_by('-date')[:10]

    # Get similar exercises
    similar_exercises = Exercise.objects.filter(
        muscle_group=exercise.muscle_group
    ).exclude(pk=exercise.pk)[:4]

    context = {
        'exercise': exercise,
        'logs': logs,
        'similar_exercises': similar_exercises
    }

    return render(request, 'workouts/exercise_detail.html', context)


@login_required
def workout_plans(request):
    form = WorkoutPlanFilterForm(request.GET)

    # Get plans created by user or public plans
    plans = WorkoutPlan.objects.filter(
        Q(created_by=request.user) | Q(is_public=True)
    ).distinct()

    # Apply filters
    if form.is_valid():
        if form.cleaned_data['search']:
            query = form.cleaned_data['search']
            plans = plans.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query)
            )

        if form.cleaned_data['goal']:
            plans = plans.filter(goal=form.cleaned_data['goal'])

        if form.cleaned_data['intensity']:
            plans = plans.filter(intensity=form.cleaned_data['intensity'])

        if form.cleaned_data['duration']:
            plans = plans.filter(duration_weeks__lte=form.cleaned_data['duration'])

    # Get user's active plans
    active_plan_ids = UserWorkoutPlan.objects.filter(
        user=request.user,
        is_active=True
    ).values_list('workout_plan_id', flat=True)

    context = {
        'plans': plans,
        'form': form,
        'active_plan_ids': active_plan_ids
    }

    return render(request, 'workouts/workout_plans.html', context)


@login_required
def plan_detail(request, pk):
    plan = get_object_or_404(WorkoutPlan, pk=pk)

    # Check if user is allowed to view this plan
    if not plan.is_public and plan.created_by != request.user:
        messages.error(request, "You don't have permission to view this workout plan.")
        return redirect('workout_plans')

    # Check if user is following this plan
    is_following = UserWorkoutPlan.objects.filter(
        user=request.user,
        workout_plan=plan,
        is_active=True
    ).exists()

    # Get exercises by day of week
    weekly_workouts = plan.get_weekly_workouts()

    context = {
        'plan': plan,
        'weekly_workouts': weekly_workouts,
        'is_following': is_following
    }

    return render(request, 'workouts/plan_detail.html', context)


@login_required
def create_plan(request):
    if request.method == 'POST':
        form = WorkoutPlanForm(request.POST)
        if form.is_valid():
            plan = form.save(commit=False)
            plan.created_by = request.user
            plan.save()

            messages.success(request, "Workout plan created successfully! Now add exercises to your plan.")
            return redirect('edit_plan', pk=plan.pk)
    else:
        form = WorkoutPlanForm()

    context = {
        'form': form,
        'title': 'Create Workout Plan'
    }

    return render(request, 'workouts/plan_form.html', context)


@login_required
def edit_plan(request, pk):
    plan = get_object_or_404(WorkoutPlan, pk=pk)

    # Check if user is allowed to edit this plan
    if plan.created_by != request.user:
        messages.error(request, "You don't have permission to edit this workout plan.")
        return redirect('workout_plans')

    if request.method == 'POST':
        form = WorkoutPlanForm(request.POST, instance=plan)
        formset = PlanExerciseFormSet(request.POST, instance=plan)

        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()

            messages.success(request, "Workout plan updated successfully!")
            return redirect('plan_detail', pk=plan.pk)
    else:
        form = WorkoutPlanForm(instance=plan)
        formset = PlanExerciseFormSet(instance=plan)

    context = {
        'form': form,
        'formset': formset,
        'plan': plan,
        'title': 'Edit Workout Plan'
    }

    return render(request, 'workouts/plan_edit.html', context)


@login_required
def delete_plan(request, pk):
    plan = get_object_or_404(WorkoutPlan, pk=pk)

    # Check if user is allowed to delete this plan
    if plan.created_by != request.user:
        messages.error(request, "You don't have permission to delete this workout plan.")
        return redirect('workout_plans')

    if request.method == 'POST':
        plan.delete()
        messages.success(request, "Workout plan deleted successfully!")
        return redirect('workout_plans')

    context = {
        'plan': plan
    }

    return render(request, 'workouts/plan_confirm_delete.html', context)


@login_required
def follow_plan(request, pk):
    plan = get_object_or_404(WorkoutPlan, pk=pk)

    # Check if user is already following this plan
    existing_plan = UserWorkoutPlan.objects.filter(
        user=request.user,
        workout_plan=plan,
        is_active=True
    ).first()

    if existing_plan:
        messages.info(request, "You are already following this workout plan.")
        return redirect('plan_detail', pk=plan.pk)

    # Create new user workout plan
    UserWorkoutPlan.objects.create(
        user=request.user,
        workout_plan=plan,
        start_date=timezone.now().date()
    )

    messages.success(request, f"You are now following the '{plan.name}' workout plan!")
    return redirect('plan_detail', pk=plan.pk)


@login_required
def unfollow_plan(request, pk):
    plan = get_object_or_404(WorkoutPlan, pk=pk)

    # Get user's active plan
    user_plan = UserWorkoutPlan.objects.filter(
        user=request.user,
        workout_plan=plan,
        is_active=True
    ).first()

    if not user_plan:
        messages.info(request, "You are not following this workout plan.")
        return redirect('plan_detail', pk=plan.pk)

    if request.method == 'POST':
        # Deactivate the plan instead of deleting
        user_plan.is_active = False
        user_plan.end_date = timezone.now().date()
        user_plan.save()

        messages.success(request, f"You have unfollowed the '{plan.name}' workout plan.")
        return redirect('workout_plans')

    context = {
        'plan': plan
    }

    return render(request, 'workouts/plan_confirm_unfollow.html', context)


@login_required
def schedule_workout(request):
    if request.method == 'POST':
        form = WorkoutScheduleForm(request.POST, user=request.user)
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.user = request.user
            schedule.save()

            messages.success(request, "Workout scheduled successfully!")
            return redirect('schedule')
    else:
        form = WorkoutScheduleForm(user=request.user)

    context = {
        'form': form,
        'title': 'Schedule Workout'
    }

    return render(request, 'workouts/schedule_form.html', context)


@login_required
def schedule(request):
    today = timezone.now().date()
    start_date = today - timedelta(days=today.weekday())
    end_date = start_date + timedelta(days=6)

    # Get next 7 days for weekly view
    week_dates = [start_date + timedelta(days=i) for i in range(7)]

    # Get schedules for this week
    schedules = WorkoutSchedule.objects.filter(
        user=request.user,
        date__range=[start_date, end_date]
    ).order_by('date', 'start_time')

    # Organize schedules by day
    schedule_by_day = {day: [] for day in week_dates}
    for schedule in schedules:
        schedule_by_day[schedule.date].append(schedule)

    # Get active plans for sidebar
    active_plans = UserWorkoutPlan.objects.filter(
        user=request.user,
        is_active=True
    ).select_related('workout_plan')

    context = {
        'week_dates': week_dates,
        'schedule_by_day': schedule_by_day,
        'active_plans': active_plans,
        'today': today
    }

    return render(request, 'workouts/schedule.html', context)


@login_required
def log_workout(request, schedule_id):
    schedule = get_object_or_404(WorkoutSchedule, pk=schedule_id, user=request.user)
    exercises = schedule.get_exercises()

    if request.method == 'POST':
        all_valid = True
        forms = []

        # Process each exercise form
        for exercise in exercises:
            prefix = f"exercise_{exercise.id}"
            form = UserPlanExerciseForm(
                request.POST,
                prefix=prefix,
                instance=UserPlanExercise(
                    user=request.user,
                    plan_exercise=exercise,
                    date=schedule.date
                )
            )

            if form.is_valid():
                forms.append(form)
            else:
                all_valid = False

        if all_valid:
            # Save all forms
            for form in forms:
                form.save()

            # Mark schedule as completed
            schedule.mark_as_completed()

            # Create workout log
            WorkoutLog.objects.create(
                user=request.user,
                date=schedule.date,
                duration=None,
                notes=""
            )

            messages.success(request, "Workout logged successfully!")
            return redirect('schedule')
    else:
        # Initialize forms for each exercise
        for exercise in exercises:
            # Check if there's already a log
            existing_log = UserPlanExercise.objects.filter(
                user=request.user,
                plan_exercise=exercise,
                date=schedule.date
            ).first()

            if existing_log:
                exercise.form = UserPlanExerciseForm(
                    instance=existing_log,
                    prefix=f"exercise_{exercise.id}"
                )
            else:
                # Try to get previous logs for weight suggestion
                previous_log = UserPlanExercise.objects.filter(
                    user=request.user,
                    plan_exercise__exercise=exercise.exercise
                ).order_by('-date').first()

                initial_data = {}
                if previous_log:
                    initial_data['weight'] = previous_log.weight

                exercise.form = UserPlanExerciseForm(
                    initial=initial_data,
                    prefix=f"exercise_{exercise.id}"
                )

    context = {
        'schedule': schedule,
        'exercises': exercises
    }

    return render(request, 'workouts/log_workout.html', context)


@login_required
def mark_workout_completed(request, schedule_id):
    schedule = get_object_or_404(WorkoutSchedule, pk=schedule_id, user=request.user)

    if request.method == 'POST':
        schedule.mark_as_completed()

        # Create workout log
        WorkoutLog.objects.create(
            user=request.user,
            date=schedule.date,
            duration=None,
            notes="Marked as completed (no details logged)"
        )

        messages.success(request, "Workout marked as completed!")

        # Redirect back to referring page
        next_page = request.POST.get('next', 'schedule')
        return redirect(next_page)

    return redirect('schedule')


@login_required
def generate_ai_plan(request):
    """Generate a workout plan using OpenAI (simplified version)"""
    if request.method == 'POST':
        goal = request.POST.get('goal')
        fitness_level = request.POST.get('fitness_level')
        days_per_week = int(request.POST.get('days_per_week', 3))

        # In a real implementation, this would call OpenAI API
        # For now, create a basic plan based on inputs

        plan = WorkoutPlan(
            name=f"{fitness_level.capitalize()} {goal.replace('_', ' ').title()} Plan",
            description=f"Custom {days_per_week}-day {fitness_level} workout plan for {goal.replace('_', ' ')}.",
            goal=goal,
            intensity='medium' if fitness_level == 'intermediate' else (
                'low' if fitness_level == 'beginner' else 'high'),
            duration_weeks=8,
            created_by=request.user,
            is_public=False
        )
        plan.save()

        # Add some basic exercises (would be more sophisticated with AI)
        muscles = MuscleGroup.objects.all()
        exercises = Exercise.objects.filter(difficulty=fitness_level)

        if exercises.exists() and muscles.exists():
            for day in range(days_per_week):
                # Simple logic to distribute muscle groups across days
                muscle_index = day % muscles.count()
                muscle = muscles[muscle_index]

                # Get exercises for this muscle group
                muscle_exercises = exercises.filter(muscle_group=muscle)

                # Add exercises to plan
                for i, exercise in enumerate(muscle_exercises[:3]):
                    PlanExercise.objects.create(
                        workout_plan=plan,
                        exercise=exercise,
                        day_of_week=day,
                        order=i,
                        sets=3,
                        reps='8-12',
                        rest_time=60
                    )

        messages.success(request, "AI Workout Plan generated successfully!")
        return redirect('plan_detail', pk=plan.pk)

    context = {
        'fitness_levels': [choice[0] for choice in Exercise.DIFFICULTY_CHOICES],
        'goals': [choice[0] for choice in WorkoutPlan.GOAL_CHOICES]
    }

    return render(request, 'workouts/generate_ai_plan.html', context)