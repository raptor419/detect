from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User, Group
from django.core.exceptions import ObjectDoesNotExist
from django.db.utils import ProgrammingError
from guardian.shortcuts import assign_perm

from nodeodm.models import ProcessingNode
from . import signals, scheduler
import logging, os
from .models import Task
from webodm import settings


def boot():
    logger = logging.getLogger('app.logger')

    # Check default group
    try:
        default_group, created = Group.objects.get_or_create(name='Default')
        if created:
            logger.info("Created default group")

            # Assign viewprocessing node object permission to default processing node (if present)
            # Otherwise non-root users will not be able to process
            try:
                pnode = ProcessingNode.objects.get(hostname="node-odm-1")
                assign_perm('view_processingnode', default_group, pnode)
                logger.info("Added view_processingnode permissions to default group")
            except ObjectDoesNotExist:
                pass


        # Add default permissions (view_project, change_project, delete_project, etc.)
        for permission in ('_project', '_task'):
            default_group.permissions.add(
                *list(Permission.objects.filter(codename__endswith=permission))
            )

        # Add permission to view processing nodes
        default_group.permissions.add(Permission.objects.get(codename="view_processingnode"))

        # Check super user
        if User.objects.filter(is_superuser=True).count() == 0:
            User.objects.create_superuser('admin', 'admin@example.com', 'admin')
            logger.info("Created superuser")

        # Unlock any Task that might have been locked
        Task.objects.filter(processing_lock=True).update(processing_lock=False)

        if not settings.TESTING:
            # Setup and start scheduler
            scheduler.setup()

            scheduler.update_nodes_info(background=True)

    except ProgrammingError:
        logger.warning("Could not touch the database. If running a migration, this is expected.")