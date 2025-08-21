import logging
import os

from datetime import datetime

from django.conf import settings
from django.contrib.sites.models import Site


from .abstract_models import AbstractNewsletter, AbstractSubscription, AbstractArticle, AbstractAttachment, \
    AbstractSubmission


logger = logging.getLogger('django')

AUTH_USER_MODEL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')


class Newsletter(AbstractNewsletter):
    pass

class Subscription(AbstractSubscription):
    pass


class Article(AbstractArticle):
    pass


def attachment_upload_to(instance, filename):
    return os.path.join(
        'newsletter', 'attachments',
        datetime.utcnow().strftime('%Y-%m-%d'),
        str(instance.message.id),
        filename
    )


class Attachment(AbstractAttachment):
    pass


def get_default_newsletter():
    return Newsletter.get_default()


class Message(AbstractArticle):
    pass

class Submission(AbstractSubmission):
   pass

def get_address(name, email):
    if name:
        return f'{name} <{email}>'
    else:
        return '%s' % email
