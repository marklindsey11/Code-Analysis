# Generated by Django 3.1.12 on 2022-03-10 05:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('codeproj', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='scan',
            name='closing_time',
            field=models.DateTimeField(blank=True, null=True, verbose_name='结果入库时间'),
        ),
        migrations.AddField(
            model_name='scan',
            name='job_archived',
            field=models.BooleanField(blank=True, null=True, verbose_name='job是否已归档'),
        ),
    ]