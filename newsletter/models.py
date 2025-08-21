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

    class Meta(AbstractNewsletter.Meta):
        swappable = "NEWSLETTER_NEWSLETTER_MODEL"
        db_table  = "newsletter_newsletter"


class Subscription(AbstractSubscription):

    class Meta(AbstractSubscription.Meta):
        swappable = "NEWSLETTER_SUBSCRIPTION_MODEL"
        db_table  = "newsletter_subscription"


class Article(AbstractArticle):

    class Meta(AbstractArticle.Meta):
        swappable = "NEWSLETTER_ARTICLE_MODEL"
        db_table  = "newsletter_article"


class Attachment(AbstractAttachment):

    class Meta(AbstractAttachment.Meta):
        swappable = "NEWSLETTER_ATTACHMENT_MODEL"
        db_table  = "newsletter_attachment"


class Message(AbstractArticle):

    class Meta(AbstractArticle.Meta):
        swappable = "NEWSLETTER_MESSAGE_MODEL"
        db_table  = "newsletter_message"



class Submission(AbstractSubmission):

   class Meta(AbstractSubmission.Meta):
        swappable = "NEWSLETTER_SUBMISSION_MODEL"
        db_table  = "newsletter_submission"
