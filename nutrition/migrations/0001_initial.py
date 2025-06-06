# Generated by Django 4.2.10 on 2025-04-07 08:54

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FoodItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("description", models.TextField(blank=True)),
                ("serving_size", models.CharField(max_length=50)),
                ("calories", models.PositiveIntegerField()),
                ("protein", models.FloatField(help_text="Protein in grams")),
                ("carbs", models.FloatField(help_text="Carbohydrates in grams")),
                ("fat", models.FloatField(help_text="Fat in grams")),
                ("fiber", models.FloatField(default=0, help_text="Fiber in grams")),
                ("sugar", models.FloatField(default=0, help_text="Sugar in grams")),
                (
                    "external_id",
                    models.CharField(
                        blank=True, help_text="ID from external API", max_length=100
                    ),
                ),
                ("image_url", models.URLField(blank=True)),
                ("is_user_created", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_foods",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Meal",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "meal_type",
                    models.CharField(
                        choices=[
                            ("breakfast", "Breakfast"),
                            ("lunch", "Lunch"),
                            ("dinner", "Dinner"),
                            ("snack", "Snack"),
                            ("pre_workout", "Pre-Workout"),
                            ("post_workout", "Post-Workout"),
                        ],
                        max_length=20,
                    ),
                ),
                ("date", models.DateField(default=django.utils.timezone.now)),
                ("name", models.CharField(blank=True, max_length=100)),
                ("notes", models.TextField(blank=True)),
            ],
            options={
                "ordering": ["date", "meal_type"],
            },
        ),
        migrations.CreateModel(
            name="MealPlan",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("description", models.TextField(blank=True)),
                (
                    "goal",
                    models.CharField(
                        choices=[
                            ("weight_loss", "Weight Loss"),
                            ("maintenance", "Maintenance"),
                            ("muscle_gain", "Muscle Gain"),
                        ],
                        max_length=20,
                    ),
                ),
                ("calories_target", models.PositiveIntegerField()),
                (
                    "protein_target",
                    models.PositiveIntegerField(help_text="Target protein in grams"),
                ),
                (
                    "carbs_target",
                    models.PositiveIntegerField(help_text="Target carbs in grams"),
                ),
                (
                    "fat_target",
                    models.PositiveIntegerField(help_text="Target fat in grams"),
                ),
                ("is_ai_generated", models.BooleanField(default=False)),
                ("start_date", models.DateField(default=django.utils.timezone.now)),
                ("end_date", models.DateField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="meal_plans",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="MealItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("servings", models.FloatField(default=1.0)),
                ("notes", models.CharField(blank=True, max_length=200)),
                (
                    "food_item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="nutrition.fooditem",
                    ),
                ),
                (
                    "meal",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="nutrition.meal",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
        migrations.AddField(
            model_name="meal",
            name="meal_plan",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="meals",
                to="nutrition.mealplan",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="meal",
            unique_together={("meal_plan", "meal_type", "date")},
        ),
        migrations.CreateModel(
            name="DailyNutritionLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("date", models.DateField(default=django.utils.timezone.now)),
                (
                    "calories_consumed",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                (
                    "protein_consumed",
                    models.FloatField(
                        blank=True, help_text="Protein in grams", null=True
                    ),
                ),
                (
                    "carbs_consumed",
                    models.FloatField(
                        blank=True, help_text="Carbohydrates in grams", null=True
                    ),
                ),
                (
                    "fat_consumed",
                    models.FloatField(blank=True, help_text="Fat in grams", null=True),
                ),
                (
                    "water_consumed",
                    models.FloatField(
                        blank=True, help_text="Water in liters", null=True
                    ),
                ),
                ("calories_target", models.PositiveIntegerField(blank=True, null=True)),
                ("protein_target", models.FloatField(blank=True, null=True)),
                ("carbs_target", models.FloatField(blank=True, null=True)),
                ("fat_target", models.FloatField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("is_cheat_day", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="nutrition_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-date"],
                "unique_together": {("user", "date")},
            },
        ),
    ]
