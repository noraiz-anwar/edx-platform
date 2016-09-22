# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('grades', '0004_visibleblocks_course_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='visibleblocks',
            name='version',
            field=models.IntegerField(default=1),
            preserve_default=False,
        ),
    ]
