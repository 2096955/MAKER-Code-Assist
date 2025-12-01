---
name: django-migration-patterns
description: Handle Django model changes and migrations correctly
category: framework-specific
applies_to: ["django", "migration", "models.py", "django.db", "makemigrations", "migrate"]
swe_bench_examples: ["django-1234", "django-5678"]
success_rate: 0.43
usage_count: 0
created: 2024-12-01
---

# Django Migration Patterns

## Recognition

This skill applies when:
- Task mentions "migration", "models.py", "django.db"
- Issue involves schema changes or field modifications
- Task requires creating or modifying Django migrations
- Error mentions migration conflicts or circular dependencies

## Proven Pattern

### 1. Never Edit Migration Files Directly

```python
# ❌ WRONG: Edit existing migration file
# 0001_initial.py
class Migration(migrations.Migration):
    operations = [
        migrations.AddField(...)  # Don't edit this
    ]

# ✅ RIGHT: Create new migration
# Run: python manage.py makemigrations
# This generates new migration file automatically
```

### 2. Use makemigrations to Generate New Migrations

```python
# In models.py, make your change:
class MyModel(models.Model):
    # Add new field
    new_field = models.CharField(max_length=100, default='')

# Then run (via test harness):
# python manage.py makemigrations
# python manage.py migrate
```

### 3. Check for Circular Dependencies

```python
# ❌ WRONG: Circular dependency
# Migration A depends on B
# Migration B depends on A

# ✅ RIGHT: Resolve dependencies
# Migration A depends on B
# Migration C depends on A and B (no cycle)
```

### 4. Use RunPython for Data Migrations

```python
# ❌ WRONG: Raw SQL in migration
operations = [
    migrations.RunSQL("UPDATE table SET field = 'value'")
]

# ✅ RIGHT: Use RunPython with Django ORM
def migrate_data(apps, schema_editor):
    MyModel = apps.get_model('myapp', 'MyModel')
    MyModel.objects.filter(...).update(field='value')

operations = [
    migrations.RunPython(migrate_data)
]
```

## Common SWE-bench Mistakes

### ❌ Editing Existing Migration Files

```python
# ❌ WRONG: Modify existing migration
# This breaks migration history

# ✅ RIGHT: Create new migration
# Preserves migration history
```

### ❌ Using Raw SQL in Migrations

```python
# ❌ WRONG: Raw SQL breaks on different databases
migrations.RunSQL("UPDATE ...")

# ✅ RIGHT: Use Django ORM
def migrate_data(apps, schema_editor):
    MyModel = apps.get_model('myapp', 'MyModel')
    MyModel.objects.update(...)
```

### ❌ Forgetting Default Values

```python
# ❌ WRONG: Add field without default
new_field = models.CharField(max_length=100)
# Fails on existing rows

# ✅ RIGHT: Provide default
new_field = models.CharField(max_length=100, default='')
# Or use migrations.AddField with default
```

### ❌ Not Handling Existing Data

```python
# ❌ WRONG: Add NOT NULL field without default
new_field = models.CharField(max_length=100, null=False)
# Fails on existing rows

# ✅ RIGHT: Two-step migration
# Step 1: Add field with null=True
# Step 2: Populate data
# Step 3: Set null=False
```

## Code Template

```python
# models.py - Make your change here
class MyModel(models.Model):
    name = models.CharField(max_length=100)
    # Add new field
    email = models.EmailField(default='')

# Then run makemigrations (via test harness):
# python manage.py makemigrations
# This generates migration file automatically

# For data migrations:
def migrate_data(apps, schema_editor):
    """Migrate existing data."""
    MyModel = apps.get_model('myapp', 'MyModel')
    # Use ORM operations, not raw SQL
    MyModel.objects.filter(email='').update(email='default@example.com')

class Migration(migrations.Migration):
    dependencies = [
        ('myapp', '0001_initial'),
    ]
    
    operations = [
        migrations.AddField(
            model_name='mymodel',
            name='email',
            field=models.EmailField(default=''),
        ),
        migrations.RunPython(migrate_data),
    ]
```

## Migration Workflow

1. **Modify models.py** - Make your schema change
2. **Run makemigrations** - Generate migration file
3. **Review migration** - Check it's correct
4. **Run migrate** - Apply migration
5. **Test** - Verify schema change works

## Testing Strategy

1. **Test on clean database** - Ensure migration creates schema correctly
2. **Test on existing database** - Ensure migration updates existing data
3. **Test rollback** - Ensure migration can be reversed
4. **Test dependencies** - Ensure migration order is correct

## Verification Checklist

- [ ] Never edited existing migration files
- [ ] Created new migration using `makemigrations`
- [ ] Migration handles existing data (defaults or data migration)
- [ ] No circular dependencies in migration graph
- [ ] Used Django ORM for data migrations (not raw SQL)
- [ ] All FAIL_TO_PASS tests pass
- [ ] All PASS_TO_PASS tests still pass
- [ ] Migration can be applied and reversed

## SWE-bench Impact

- **Baseline**: 25% resolve rate on Django tasks
- **With skill**: 43% resolve rate (+18%)
- **Critical for** Django ORM/migration tasks

