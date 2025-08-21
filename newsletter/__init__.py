from importlib.metadata import version, PackageNotFoundError
from django.conf import settings

try:
    __version__ = version("django-newsletter")
except PackageNotFoundError:
    # package is not installed
    __version__ = None

NEWSLETTER_NEWSLETTER_MODEL = getattr(settings, "NEWSLETTER_NEWSLETTER_MODEL", "newsletter.Newsletter")
NEWSLETTER_MESSAGE_MODEL    = getattr(settings, "NEWSLETTER_MESSAGE_MODEL", "newsletter.Message")
NEWSLETTER_SUBSCRIPTION_MODEL = getattr(settings, "NEWSLETTER_SUBSCRIPTION_MODEL", "newsletter.Subscription")
NEWSLETTER_SUBMISSION_MODEL = getattr(settings, "NEWSLETTER_SUBMISSION_MODEL", "newsletter.Submission")
NEWSLETTER_ARTICLE_MODEL    = getattr(settings, "NEWSLETTER_ARTICLE_MODEL", "newsletter.Article")
NEWSLETTER_ATTACHMENT_MODEL = getattr(settings, "NEWSLETTER_ATTACHMENT_MODEL", "newsletter.Attachment")
