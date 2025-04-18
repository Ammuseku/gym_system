from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Avg, Sum
from datetime import timedelta
from .models import FoodItem, MealPlan, Meal, MealItem, DailyNutritionLog
from .forms import (
    FoodItemForm, MealPlanForm, MealForm, MealItemForm, DailyNutritionLogForm,
    FoodSearchForm, NutritionDateRangeForm, AIGeneratedMealPlanForm
)
import requests
import json
import os
from dotenv import load_dotenv
import openai

# Load environment variables
load_dotenv()


@login_required
def nutrition_dashboard(request):
    """Main nutrition dashboard view"""
    # Get active meal plan
    active_plan = MealPlan.objects.filter(
        user=request.user,
        is_active=True
    ).first()

    # Get today's meals if active plan exists
    today = timezone.now().date()
    today_meals = []
    if active_plan:
        today_meals = Meal.objects.filter(
            meal_plan=active_plan,
            date=today
        ).order_by('meal_type')

    # Get recent nutrition logs
    recent_logs = DailyNutritionLog.objects.filter(
        user=request.user
    ).order_by('-date')[:5]

    # Check if today's log exists
    today_log = DailyNutritionLog.objects.filter(
        user=request.user,
        date=today
    ).first()

    context = {
        'active_plan': active_plan,
        'today_meals': today_meals,
        'recent_logs': recent_logs,
        'today_log': today_log,
        'today': today
    }

    return render(request, 'nutrition/dashboard.html', context)


@login_required
def meal_plans(request):
    """View all meal plans"""
    user_plans = MealPlan.objects.filter(
        user=request.user
    ).order_by('-is_active', '-created_at')

    active_plan = None
    for plan in user_plans:
        if plan.is_active:
            active_plan = plan
            break

    context = {
        'plans': user_plans,
        'active_plan': active_plan
    }

    return render(request, 'nutrition/meal_plans.html', context)


@login_required
def create_meal_plan(request):
    """Create a new meal plan"""
    if request.method == 'POST':
        form = MealPlanForm(request.POST)
        if form.is_valid():
            plan = form.save(commit=False)
            plan.user = request.user

            # If this is the first plan, make it active
            if not MealPlan.objects.filter(user=request.user).exists():
                plan.is_active = True

            plan.save()

            messages.success(request, "Meal plan created successfully!")
            return redirect('meal_plan_detail', pk=plan.pk)
    else:
        # Default values based on user profile
        initial = {}
        if hasattr(request.user, 'profile'):
            profile = request.user.profile

            # Calculate TDEE (Total Daily Energy Expenditure) based on profile
            if profile.weight and profile.height and profile.gender and profile.birthdate:
                # Basic BMR calculation using Mifflin-St Jeor formula
                weight_kg = profile.weight
                height_cm = profile.height
                age = profile.age or 25  # Default to 25 if age not available

                if profile.gender == 'M':
                    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
                else:
                    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161

                # Activity multiplier
                activity_multiplier = 1.2  # Sedentary
                if profile.fitness_level == 'intermediate':
                    activity_multiplier = 1.5  # Moderate activity
                elif profile.fitness_level == 'advanced':
                    activity_multiplier = 1.7  # Very active

                tdee = int(bmr * activity_multiplier)

                # Adjust based on goal
                if profile.primary_goal == 'fat_loss':
                    calories = tdee - 500  # Deficit
                    goal = 'weight_loss'
                elif profile.primary_goal == 'muscle_gain':
                    calories = tdee + 300  # Surplus
                    goal = 'muscle_gain'
                else:
                    calories = tdee  # Maintenance
                    goal = 'maintenance'

                # Calculate macros (example: 30% protein, 40% carbs, 30% fat)
                protein_pct = 0.3
                carbs_pct = 0.4
                fat_pct = 0.3

                protein_cals = calories * protein_pct
                carbs_cals = calories * carbs_pct
                fat_cals = calories * fat_pct

                protein_g = int(protein_cals / 4)  # 4 calories per gram of protein
                carbs_g = int(carbs_cals / 4)  # 4 calories per gram of carbs
                fat_g = int(fat_cals / 9)  # 9 calories per gram of fat

                initial = {
                    'goal': goal,
                    'calories_target': calories,
                    'protein_target': protein_g,
                    'carbs_target': carbs_g,
                    'fat_target': fat_g,
                    'name': f"{profile.get_primary_goal_display()} Plan"
                }

        form = MealPlanForm(initial=initial)

    context = {
        'form': form,
        'title': 'Create Meal Plan'
    }

    return render(request, 'nutrition/meal_plan_form.html', context)


@login_required
def meal_plan_detail(request, pk):
    """View meal plan details"""
    plan = get_object_or_404(MealPlan, pk=pk, user=request.user)

    # Get meals grouped by date
    meals = Meal.objects.filter(meal_plan=plan).order_by('date', 'meal_type')

    # Group meals by date
    meals_by_date = {}
    for meal in meals:
        if meal.date not in meals_by_date:
            meals_by_date[meal.date] = []
        meals_by_date[meal.date].append(meal)

    context = {
        'plan': plan,
        'meals_by_date': meals_by_date
    }

    return render(request, 'nutrition/meal_plan_detail.html', context)


@login_required
def edit_meal_plan(request, pk):
    """Edit an existing meal plan"""
    plan = get_object_or_404(MealPlan, pk=pk, user=request.user)

    if request.method == 'POST':
        form = MealPlanForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            messages.success(request, "Meal plan updated successfully!")
            return redirect('meal_plan_detail', pk=plan.pk)
    else:
        form = MealPlanForm(instance=plan)

    context = {
        'form': form,
        'plan': plan,
        'title': 'Edit Meal Plan',
        'is_edit': True
    }

    return render(request, 'nutrition/meal_plan_form.html', context)


@login_required
def activate_meal_plan(request, pk):
    """Set a meal plan as active and deactivate others"""
    plan = get_object_or_404(MealPlan, pk=pk, user=request.user)

    # Deactivate all plans for this user
    MealPlan.objects.filter(user=request.user).update(is_active=False)

    # Activate this plan
    plan.is_active = True
    plan.save()

    messages.success(request, f"'{plan.name}' is now your active meal plan.")
    return redirect('meal_plans')


@login_required
def delete_meal_plan(request, pk):
    """Delete a meal plan"""
    plan = get_object_or_404(MealPlan, pk=pk, user=request.user)

    if request.method == 'POST':
        # Check if this is the only active plan
        was_active = plan.is_active

        # Delete the plan
        plan.delete()

        # If this was the active plan, try to activate another one
        if was_active:
            next_plan = MealPlan.objects.filter(user=request.user).order_by('-created_at').first()
            if next_plan:
                next_plan.is_active = True
                next_plan.save()

        messages.success(request, "Meal plan deleted successfully!")
        return redirect('meal_plans')

    context = {
        'plan': plan
    }

    return render(request, 'nutrition/confirm_delete_plan.html', context)


@login_required
def add_meal(request, plan_id):
    """Add a meal to a meal plan"""
    plan = get_object_or_404(MealPlan, pk=plan_id, user=request.user)

    if request.method == 'POST':
        form = MealForm(request.POST, meal_plan=plan)
        if form.is_valid():
            meal = form.save()
            messages.success(request, "Meal added successfully!")
            return redirect('meal_detail', pk=meal.pk)
    else:
        form = MealForm(meal_plan=plan)

    context = {
        'form': form,
        'plan': plan,
        'title': 'Add Meal'
    }

    return render(request, 'nutrition/meal_form.html', context)


@login_required
def meal_detail(request, pk):
    """View meal details and food items"""
    meal = get_object_or_404(Meal, pk=pk, meal_plan__user=request.user)

    # Get food items for this meal
    items = MealItem.objects.filter(meal=meal).select_related('food_item')

    # Calculate meal totals
    total_calories = 0
    total_protein = 0
    total_carbs = 0
    total_fat = 0

    for item in items:
        total_calories += item.get_calories()
        total_protein += item.get_protein()
        total_carbs += item.get_carbs()
        total_fat += item.get_fat()

    context = {
        'meal': meal,
        'items': items,
        'totals': {
            'calories': total_calories,
            'protein': total_protein,
            'carbs': total_carbs,
            'fat': total_fat
        }
    }

    return render(request, 'nutrition/meal_detail.html', context)


@login_required
def edit_meal(request, pk):
    """Edit a meal"""
    meal = get_object_or_404(Meal, pk=pk, meal_plan__user=request.user)

    if request.method == 'POST':
        form = MealForm(request.POST, instance=meal, meal_plan=meal.meal_plan)
        if form.is_valid():
            form.save()
            messages.success(request, "Meal updated successfully!")
            return redirect('meal_detail', pk=meal.pk)
    else:
        form = MealForm(instance=meal, meal_plan=meal.meal_plan)

    context = {
        'form': form,
        'meal': meal,
        'title': 'Edit Meal',
        'is_edit': True
    }

    return render(request, 'nutrition/meal_form.html', context)


@login_required
def delete_meal(request, pk):
    """Delete a meal"""
    meal = get_object_or_404(Meal, pk=pk, meal_plan__user=request.user)
    plan_id = meal.meal_plan.id

    if request.method == 'POST':
        meal.delete()
        messages.success(request, "Meal deleted successfully!")
        return redirect('meal_plan_detail', pk=plan_id)

    context = {
        'meal': meal
    }

    return render(request, 'nutrition/confirm_delete_meal.html', context)


@login_required
def add_food_to_meal(request, meal_id):
    """Add a food item to a meal"""
    meal = get_object_or_404(Meal, pk=meal_id, meal_plan__user=request.user)

    if request.method == 'POST':
        form = MealItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.meal = meal
            item.save()

            messages.success(request, "Food item added successfully!")
            return redirect('meal_detail', pk=meal.pk)
    else:
        form = MealItemForm()

    context = {
        'form': form,
        'meal': meal,
        'title': 'Add Food to Meal'
    }

    return render(request, 'nutrition/meal_item_form.html', context)


@login_required
def edit_meal_item(request, pk):
    """Edit a food item in a meal"""
    item = get_object_or_404(MealItem, pk=pk, meal__meal_plan__user=request.user)

    if request.method == 'POST':
        form = MealItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, "Food item updated successfully!")
            return redirect('meal_detail', pk=item.meal.pk)
    else:
        form = MealItemForm(instance=item)

    context = {
        'form': form,
        'item': item,
        'meal': item.meal,
        'title': 'Edit Food Item',
        'is_edit': True
    }

    return render(request, 'nutrition/meal_item_form.html', context)


@login_required
def delete_meal_item(request, pk):
    """Delete a food item from a meal"""
    item = get_object_or_404(MealItem, pk=pk, meal__meal_plan__user=request.user)
    meal_id = item.meal.id

    if request.method == 'POST':
        item.delete()
        messages.success(request, "Food item removed successfully!")
        return redirect('meal_detail', pk=meal_id)

    context = {
        'item': item,
        'meal': item.meal
    }

    return render(request, 'nutrition/confirm_delete_meal_item.html', context)


@login_required
def food_library(request):
    """View food library and search for foods"""
    query = request.GET.get('query', '')

    if query:
        # Search for foods
        foods = FoodItem.objects.filter(name__icontains=query).order_by('name')
    else:
        # Get all foods, prioritizing user-created ones
        foods = FoodItem.objects.all().order_by('-is_user_created', 'name')[:100]

    # Create search form
    form = FoodSearchForm(initial={'query': query} if query else None)

    context = {
        'foods': foods,
        'form': form,
        'query': query
    }

    return render(request, 'nutrition/food_library.html', context)


@login_required
def add_food(request):
    """Add a new food item to the library"""
    if request.method == 'POST':
        form = FoodItemForm(request.POST)
        if form.is_valid():
            food = form.save(commit=False)
            food.is_user_created = True
            food.created_by = request.user
            food.save()

            messages.success(request, "Food item added successfully!")
            return redirect('food_library')
    else:
        form = FoodItemForm()

    context = {
        'form': form,
        'title': 'Add Food Item'
    }

    return render(request, 'nutrition/food_form.html', context)


@login_required
def food_detail(request, pk):
    """View food item details"""
    food = get_object_or_404(FoodItem, pk=pk)

    context = {
        'food': food
    }

    return render(request, 'nutrition/food_detail.html', context)


@login_required
def edit_food(request, pk):
    """Edit a food item"""
    food = get_object_or_404(FoodItem, pk=pk)

    # Only allow editing if food is user created and created by this user
    if not food.is_user_created or food.created_by != request.user:
        messages.error(request, "You cannot edit this food item.")
        return redirect('food_detail', pk=food.pk)

    if request.method == 'POST':
        form = FoodItemForm(request.POST, instance=food)
        if form.is_valid():
            form.save()
            messages.success(request, "Food item updated successfully!")
            return redirect('food_detail', pk=food.pk)
    else:
        form = FoodItemForm(instance=food)

    context = {
        'form': form,
        'food': food,
        'title': 'Edit Food Item',
        'is_edit': True
    }

    return render(request, 'nutrition/food_form.html', context)


@login_required
def delete_food(request, pk):
    """Delete a food item"""
    food = get_object_or_404(FoodItem, pk=pk)

    # Only allow deletion if food is user created and created by this user
    if not food.is_user_created or food.created_by != request.user:
        messages.error(request, "You cannot delete this food item.")
        return redirect('food_detail', pk=food.pk)

    if request.method == 'POST':
        food.delete()
        messages.success(request, "Food item deleted successfully!")
        return redirect('food_library')

    context = {
        'food': food
    }

    return render(request, 'nutrition/confirm_delete_food.html', context)


@login_required
def log_nutrition(request):
    """Log daily nutrition"""
    if request.method == 'POST':
        form = DailyNutritionLogForm(request.POST, user=request.user)
        if form.is_valid():
            log = form.save()
            messages.success(request, "Nutrition logged successfully!")
            return redirect('nutrition_logs')
    else:
        # Check if log exists for today
        today = timezone.now().date()
        existing_log = DailyNutritionLog.objects.filter(
            user=request.user,
            date=today
        ).first()

        if existing_log:
            # Edit existing log
            form = DailyNutritionLogForm(instance=existing_log, user=request.user)
            is_edit = True
        else:
            # Create new log
            form = DailyNutritionLogForm(user=request.user)
            is_edit = False

    context = {
        'form': form,
        'title': 'Log Nutrition',
        'is_edit': is_edit if 'is_edit' in locals() else False
    }

    return render(request, 'nutrition/log_nutrition.html', context)


@login_required
def nutrition_logs(request):
    """View nutrition logs history"""
    # Create filter form
    form = NutritionDateRangeForm(request.GET)

    # Get all logs
    logs = DailyNutritionLog.objects.filter(user=request.user).order_by('-date')

    # Apply filters if form is valid
    if form.is_valid():
        start_date = form.cleaned_data.get('start_date')
        end_date = form.cleaned_data.get('end_date')

        if start_date:
            logs = logs.filter(date__gte=start_date)

        if end_date:
            logs = logs.filter(date__lte=end_date)

    context = {
        'logs': logs,
        'form': form
    }

    return render(request, 'nutrition/nutrition_logs.html', context)


@login_required
def delete_nutrition_log(request, pk):
    """Delete a nutrition log"""
    log = get_object_or_404(DailyNutritionLog, pk=pk, user=request.user)

    if request.method == 'POST':
        log.delete()
        messages.success(request, "Nutrition log deleted successfully!")
        return redirect('nutrition_logs')

    context = {
        'log': log
    }

    return render(request, 'nutrition/confirm_delete_log.html', context)


@login_required
def search_spoonacular(request):
    """Search for foods using Spoonacular API"""
    api_key = os.getenv('SPOONACULAR_API_KEY')

    if not api_key:
        messages.error(request, "Spoonacular API key is not configured.")
        return redirect('food_library')

    query = request.GET.get('query', '')
    results = []

    if query:
        try:
            # Make API request to Spoonacular
            url = f"https://api.spoonacular.com/food/ingredients/search"
            params = {
                'apiKey': api_key,
                'query': query,
                'number': 10,
                'metaInformation': True
            }

            response = requests.get(url, params=params)
            data = response.json()

            if 'results' in data:
                results = data['results']
        except Exception as e:
            messages.error(request, f"Error searching foods: {str(e)}")

    context = {
        'query': query,
        'results': results
    }

    return render(request, 'nutrition/search_results.html', context)


@login_required
def add_spoonacular_food(request, spoonacular_id):
    """Add a food from Spoonacular API to the food library"""
    api_key = os.getenv('SPOONACULAR_API_KEY')

    if not api_key:
        messages.error(request, "Spoonacular API key is not configured.")
        return redirect('food_library')

    try:
        # Check if food already exists
        existing_food = FoodItem.objects.filter(external_id=str(spoonacular_id)).first()
        if existing_food:
            messages.info(request, f"'{existing_food.name}' is already in your food library.")
            return redirect('food_detail', pk=existing_food.pk)

        # Get food details from Spoonacular
        url = f"https://api.spoonacular.com/food/ingredients/{spoonacular_id}/information"
        params = {
            'apiKey': api_key,
            'amount': 100,
            'unit': 'grams'
        }

        response = requests.get(url, params=params)
        data = response.json()

        if 'name' in data:
            # Extract nutrition data
            nutrients = {}
            for nutrient in data.get('nutrition', {}).get('nutrients', []):
                nutrients[nutrient['name'].lower()] = nutrient['amount']

            # Create new food item
            food = FoodItem(
                name=data['name'].title(),
                description=f"Imported from Spoonacular - {data.get('original', '')}",
                serving_size="100g",
                calories=int(nutrients.get('calories', 0)),
                protein=round(nutrients.get('protein', 0), 1),
                carbs=round(nutrients.get('carbohydrates', 0), 1),
                fat=round(nutrients.get('fat', 0), 1),
                fiber=round(nutrients.get('fiber', 0), 1),
                sugar=round(nutrients.get('sugar', 0), 1),
                external_id=str(spoonacular_id),
                image_url=f"https://spoonacular.com/cdn/ingredients_100x100/{data.get('image', '')}",
                is_user_created=False
            )

            food.save()

            messages.success(request, f"'{food.name}' added to your food library.")
            return redirect('food_detail', pk=food.pk)
        else:
            messages.error(request, "Could not retrieve food information.")

    except Exception as e:
        messages.error(request, f"Error adding food: {str(e)}")

    return redirect('food_library')


@login_required
def generate_ai_meal_plan(request):
    """Generate a meal plan using OpenAI"""
    openai_api_key = os.getenv('OPENAI_API_KEY')

    if not openai_api_key:
        messages.error(request, "OpenAI API key is not configured.")
        return redirect('meal_plans')

    if request.method == 'POST':
        form = AIGeneratedMealPlanForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data.get('name')
            goal = form.cleaned_data.get('goal')
            calories = form.cleaned_data.get('calories_per_day')
            restrictions = form.cleaned_data.get('dietary_restrictions', '')
            days = form.cleaned_data.get('days_to_generate')

            try:
                # Calculate macros based on goal
                if goal == 'weight_loss':
                    protein_pct = 0.35  # Higher protein for weight loss
                    carbs_pct = 0.35
                    fat_pct = 0.30
                elif goal == 'muscle_gain':
                    protein_pct = 0.30
                    carbs_pct = 0.45  # Higher carbs for muscle gain
                    fat_pct = 0.25
                else:  # maintenance
                    protein_pct = 0.30
                    carbs_pct = 0.40
                    fat_pct = 0.30

                protein_cals = calories * protein_pct
                carbs_cals = calories * carbs_pct
                fat_cals = calories * fat_pct

                protein_g = int(protein_cals / 4)
                carbs_g = int(carbs_cals / 4)
                fat_g = int(fat_cals / 9)

                # Create meal plan in database
                plan = MealPlan.objects.create(
                    user=request.user,
                    name=name,
                    description=f"AI-generated meal plan for {goal.replace('_', ' ')}",
                    goal=goal,
                    calories_target=calories,
                    protein_target=protein_g,
                    carbs_target=carbs_g,
                    fat_target=fat_g,
                    is_ai_generated=True
                )

                # Generate the meal plan with OpenAI
                prompt = f"""Create a {days}-day meal plan for {goal.replace('_', ' ')} with approximately {calories} calories per day. 
                The daily macronutrient goals are {protein_g}g protein, {carbs_g}g carbs, and {fat_g}g fat.

                {f"Dietary restrictions: {restrictions}" if restrictions else ""}

                For each day, include breakfast, lunch, dinner, and snacks. For each meal, include the food items and approximate quantities.

                Format the response as a JSON object with the following structure:
                {{
                  "days": [
                    {{
                      "day": 1,
                      "meals": [
                        {{
                          "meal_type": "breakfast",
                          "foods": [
                            {{
                              "name": "Food name",
                              "quantity": "Quantity (e.g., 2 large eggs, 1 cup oatmeal)",
                              "calories": 300,
                              "protein": 20,
                              "carbs": 30,
                              "fat": 10
                            }}
                          ]
                        }}
                      ]
                    }}
                  ]
                }}

                Include only common foods with realistic nutritional values. Each day should meet the calorie and macronutrient targets.
                """

                # Call OpenAI API - using the updated client pattern
                client = openai.OpenAI(api_key=openai_api_key)
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are a nutrition specialist creating personalized meal plans."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                )

                # Parse the response
                meal_plan_json = json.loads(response.choices[0].message.content)

                # Create meals and food items
                today = timezone.now().date()

                for day_data in meal_plan_json['days']:
                    day_num = day_data['day']
                    day_date = today + timedelta(days=day_num - 1)

                    for meal_data in day_data['meals']:
                        meal_type = meal_data['meal_type']

                        # Create the meal
                        meal = Meal.objects.create(
                            meal_plan=plan,
                            meal_type=meal_type,
                            date=day_date,
                            name=f"Day {day_num} - {meal_type.capitalize()}"
                        )

                        # Add food items to the meal
                        for food_data in meal_data['foods']:
                            # Try to find existing food or create a new one
                            food_name = food_data['name']
                            existing_food = FoodItem.objects.filter(name__iexact=food_name).first()

                            if existing_food:
                                food = existing_food
                            else:
                                # Create a new food item
                                food = FoodItem.objects.create(
                                    name=food_name,
                                    description="Generated for AI meal plan",
                                    serving_size=food_data['quantity'],
                                    calories=food_data['calories'],
                                    protein=food_data['protein'],
                                    carbs=food_data['carbs'],
                                    fat=food_data['fat'],
                                    is_user_created=False
                                )

                            # Add to meal
                            MealItem.objects.create(
                                meal=meal,
                                food_item=food,
                                servings=1.0,
                                notes=food_data['quantity']
                            )

                messages.success(request, "AI meal plan generated successfully!")
                return redirect('meal_plan_detail', pk=plan.pk)

            except Exception as e:
                messages.error(request, f"Error generating meal plan: {str(e)}")
                return redirect('meal_plans')
    else:
        form = AIGeneratedMealPlanForm()

    context = {
        'form': form,
        'title': 'Generate AI Meal Plan'
    }

    return render(request, 'nutrition/generate_ai_meal_plan.html', context)