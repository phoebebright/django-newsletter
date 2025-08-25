import logging
import os
import time
from datetime import datetime

from django.apps import apps
from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.sites.managers import CurrentSiteManager
from django.core.mail import EmailMultiAlternatives
from django.db import models
from django.template.loader import select_template
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext
from django.utils.timezone import now
from django.urls import reverse

from .fields import DynamicImageField
from .utils import (
    make_activation_code, get_default_sites, ACTIONS
)
from .settings import newsletter_settings


logger = logging.getLogger('django')

AUTH_USER_MODEL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')

def get_newsletter_model():
    return apps.get_model(newsletter_settings.NEWSLETTER_MODEL, require_ready=False)

def get_message_model():
    return apps.get_model(newsletter_settings.MESSAGE_MODEL, require_ready=False)

def get_subscription_model():
    return apps.get_model(newsletter_settings.SUBSCRIPTION_MODEL, require_ready=False)

def get_attachment_model():
    return apps.get_model(newsletter_settings.ATTACHMENT_MODEL, require_ready=False)

def get_article_model():
    return apps.get_model(newsletter_settings.ARTICLE_MODEL, require_ready=False)

def get_submission_model():
    return apps.get_model(newsletter_settings.SUBMISSION_MODEL, require_ready=False)


def get_default_newsletter():
    Newsletter = get_newsletter_model()
    return Newsletter.get_default()

def attachment_upload_to(instance, filename):
    return os.path.join(
        'newsletter', 'attachments',
        datetime.utcnow().strftime('%Y-%m-%d'),
        str(instance.message.id),
        filename
    )

def get_address(name, email):
    if name:
        return f'{name} <{email}>'
    else:
        return '%s' % email

class AbstractNewsletter(models.Model):

    _Subscription = None
    @property
    def Subscription(self):
        if not self._Subscription:
            self._Subscription = get_subscription_model()
        return self._Subscription

    site = models.ManyToManyField(Site, default=get_default_sites)

    title = models.CharField(
        max_length=200, verbose_name=_('newsletter title')
    )
    slug = models.SlugField(db_index=True, unique=True)

    email = models.EmailField(
        verbose_name=_('e-mail'), help_text=_('Sender e-mail')
    )
    sender = models.CharField(
        max_length=200, verbose_name=_('sender'), help_text=_('Sender name')
    )

    visible = models.BooleanField(
        default=True, verbose_name=_('visible'), db_index=True
    )

    send_html = models.BooleanField(
        default=True, verbose_name=_('send html'),
        help_text=_('Whether or not to send HTML versions of e-mails.')
    )

    objects = models.Manager()

    # Automatically filter the current site
    on_site = CurrentSiteManager()

    class Meta:
        abstract = True
        verbose_name = _('newsletter')
        verbose_name_plural = _('newsletters')

    def __str__(self):
        return self.title



    def get_templates(self, action):
        """
        Return a subject, text, HTML tuple with e-mail templates for
        a particular action. Returns a tuple with subject, text and e-mail
        template.
        """

        assert action in ACTIONS + ('message',), 'Unknown action: %s' % action

        # Common substitutions for filenames
        tpl_subst = {
            'action': action,
            'newsletter': self.slug
        }

        # Common root path for all the templates
        tpl_root = 'newsletter/message/'

        subject_template = select_template([
            tpl_root + '%(newsletter)s/%(action)s_subject.txt' % tpl_subst,
            tpl_root + '%(action)s_subject.txt' % tpl_subst,
        ])

        text_template = select_template([
            tpl_root + '%(newsletter)s/%(action)s.txt' % tpl_subst,
            tpl_root + '%(action)s.txt' % tpl_subst,
        ])

        if self.send_html:
            html_template = select_template([
                tpl_root + '%(newsletter)s/%(action)s.html' % tpl_subst,
                tpl_root + '%(action)s.html' % tpl_subst,
            ])
        else:
            # HTML templates are not required
            html_template = None

        return subject_template, text_template, html_template


    def get_absolute_url(self):
        return reverse('newsletter:newsletter_detail', kwargs={'newsletter_slug': self.slug})

    def subscribe_url(self):
        return reverse('newsletter:newsletter_subscribe_request', kwargs={'newsletter_slug': self.slug})

    def unsubscribe_url(self):
        return reverse('newsletter:newsletter_unsubscribe_request', kwargs={'newsletter_slug': self.slug})

    def update_url(self):
        return reverse('newsletter:newsletter_update_request', kwargs={'newsletter_slug': self.slug})

    def archive_url(self):
        return reverse('newsletter:newsletter_archive', kwargs={'newsletter_slug': self.slug})

    def get_sender(self):
        return get_address(self.sender, self.email)

    def get_subscriptions(self):
        logger.debug('Looking up subscribers for %s', self)

        return self.Subscription.objects.filter(newsletter=self, subscribed=True)

    @classmethod
    def get_default(cls):
        try:
            return cls.objects.all()[0].pk
        except IndexError:
            return None


class AbstractSubscription(models.Model):

    _Newsletter = None
    @property
    def Newsletter(self):
        if not self._Newsletter:
            self._Newsletter = get_newsletter_model()
        return self._Newsletter

    user = models.ForeignKey(
        AUTH_USER_MODEL, blank=True, null=True, verbose_name=_('user'),
        on_delete=models.CASCADE
    )

    name_field = models.CharField(
        db_column='name', max_length=200, blank=True, null=True,
        verbose_name=_('name'), help_text=_('optional')
    )




    email_field = models.EmailField(
        db_column='email', verbose_name=_('e-mail'), db_index=True,
        blank=True, null=True
    )


    ip = models.GenericIPAddressField(_("IP address"), blank=True, null=True)

    newsletter = models.ForeignKey(
        newsletter_settings.NEWSLETTER_MODEL, verbose_name=_('newsletter'), on_delete=models.CASCADE
    )

    create_date = models.DateTimeField(editable=False, default=now)

    activation_code = models.CharField(
        verbose_name=_('activation code'), max_length=40,
        default=make_activation_code
    )

    subscribed = models.BooleanField(
        default=False, verbose_name=_('subscribed'), db_index=True
    )
    subscribe_date = models.DateTimeField(
        verbose_name=_("subscribe date"), null=True, blank=True
    )

    # This should be a pseudo-field, I reckon.
    unsubscribed = models.BooleanField(
        default=False, verbose_name=_('unsubscribed'), db_index=True
    )
    unsubscribe_date = models.DateTimeField(
        verbose_name=_("unsubscribe date"), null=True, blank=True
    )

    def __str__(self):
        if self.name:
            return _("%(name)s <%(email)s> to %(newsletter)s") % {
                'name': self.name,
                'email': self.email,
                'newsletter': self.newsletter
            }

        else:
            return _("%(email)s to %(newsletter)s") % {
                'email': self.email,
                'newsletter': self.newsletter
            }

    class Meta:
        abstract = True
        verbose_name = _('subscription')
        verbose_name_plural = _('subscriptions')
        unique_together = ('user', 'email_field', 'newsletter')




    def save(self, *args, **kwargs):
        """
        Perform some basic validation and state maintenance of Subscription.
        TODO: Move this code to a more suitable place (i.e. `clean()`) and
        cleanup the code. Refer to comment below and
        https://docs.djangoproject.com/en/dev/ref/models/instances/#django.db.models.Model.clean
        """
        assert self.user or self.email_field, \
            _('Neither an email nor a username is set. This asks for '
              'inconsistency!')
        assert ((self.user and not self.email_field) or
                (self.email_field and not self.user)), \
            _('If user is set, email must be null and vice versa.')

        # This is a lame way to find out if we have changed but using Django
        # API internals is bad practice. This is necessary to discriminate
        # from a state where we have never been subscribed but is mostly for
        # backward compatibility. It might be very useful to make this just
        # one attribute 'subscribe' later. In this case unsubscribed can be
        # replaced by a method property.

        if self.pk:
            assert (self.Subscription.objects.filter(pk=self.pk).count() == 1)

            subscription = self.Subscription.objects.get(pk=self.pk)
            old_subscribed = subscription.subscribed
            old_unsubscribed = subscription.unsubscribed

            # If we are subscribed now and we used not to be so, subscribe.
            # If we user to be unsubscribed but are not so anymore, subscribe.
            if ((self.subscribed and not old_subscribed) or
                    (old_unsubscribed and not self.unsubscribed)):
                self._subscribe()

                assert not self.unsubscribed
                assert self.subscribed

            # If we are unsubcribed now and we used not to be so, unsubscribe.
            # If we used to be subscribed but are not subscribed anymore,
            # unsubscribe.
            elif ((self.unsubscribed and not old_unsubscribed) or
                  (old_subscribed and not self.subscribed)):
                self._unsubscribe()

                assert not self.subscribed
                assert self.unsubscribed
        else:
            if self.subscribed:
                self._subscribe()
            elif self.unsubscribed:
                self._unsubscribe()

        super().save(*args, **kwargs)

    @property
    def name(self) -> str:
        if self.user:
            full = self.user.get_full_name().strip()
            if full:
                return full
            # Fallback to username or email if you want:
            return getattr(self.user, 'username', '') or getattr(self.user, 'email', '') or self.name_field or ''
        return self.name_field or ''

    @name.setter
    def name(self, value: str) -> None:
        if self.user:
            logger.warning(f"Trying to set name on a user-based subscription: {self.user}. Ignoring.")
            return
        self.name_field = value


    @property
    def email(self) -> str:
        if self.user:
            return self.user.email
        return self.email_field

    @email.setter
    def email(self, value: str) -> None:
        if self.user:
            logger.warning(f"Trying to set email on a user-based subscription: {self.user}. Ignoring.")
            return
        self.email_field = value



    def update(self, action):
        """
        Update subscription according to requested action:
        subscribe/unsubscribe/update/, then save the changes.
        """

        assert action in ('subscribe', 'update', 'unsubscribe')

        # If a new subscription or update, make sure it is subscribed
        # Else, unsubscribe
        if action == 'subscribe' or action == 'update':
            self.subscribed = True
        else:
            self.unsubscribed = True

        logger.debug(
            _('Updated subscription %(subscription)s to %(action)s.'),
            {
                'subscription': self,
                'action': action
            }
        )

        # This triggers the subscribe() and/or unsubscribe() methods, taking
        # care of stuff like maintaining the (un)subscribe date.
        self.save()

    def _subscribe(self):
        """
        Internal helper method for managing subscription state
        during subscription.
        """
        logger.debug('Subscribing subscription %s.', self)

        self.subscribe_date = now()
        self.subscribed = True
        self.unsubscribed = False
        self.unsubscribe_date = None

    def _unsubscribe(self):
        """
        Internal helper method for managing subscription state
        during unsubscription.
        """
        logger.debug('Unsubscribing subscription %s.', self)

        self.subscribed = False
        self.unsubscribed = True
        self.unsubscribe_date = now()

    def get_recipient(self):
        return get_address(self.name, self.email)

    def send_activation_email(self, action):
        assert action in ACTIONS, 'Unknown action: %s' % action

        (subject_template, text_template, html_template) = \
            self.newsletter.get_templates(action)

        variable_dict = {
            'subscription': self,
            'site': Site.objects.get_current(),
            'newsletter': self.newsletter,
            'date': self.subscribe_date,
            'STATIC_URL': settings.STATIC_URL,
            'MEDIA_URL': settings.MEDIA_URL
        }

        subject = subject_template.render(variable_dict).strip()
        text = text_template.render(variable_dict)

        message = EmailMultiAlternatives(
            subject, text,
            from_email=self.newsletter.get_sender(),
            to=[self.email]
        )

        if html_template:
            message.attach_alternative(
                html_template.render(variable_dict), "text/html"
            )

        message.send()

        logger.debug(
            'Activation email sent for action "%(action)s" to %(subscriber)s '
            'with activation code "%(action_code)s".', {
                'action_code': self.activation_code,
                'action': action,
                'subscriber': self
            }
        )

    def subscribe_activate_url(self):
        return reverse('newsletter_update_activate', kwargs={
            'newsletter_slug': self.newsletter.slug,
            'email': self.email,
            'action': 'subscribe',
            'activation_code': self.activation_code
        })

    def unsubscribe_activate_url(self):
        return reverse('newsletter_update_activate', kwargs={
            'newsletter_slug': self.newsletter.slug,
            'email': self.email,
            'action': 'unsubscribe',
            'activation_code': self.activation_code
        })

    def update_activate_url(self):
        return reverse('newsletter_update_activate', kwargs={
            'newsletter_slug': self.newsletter.slug,
            'email': self.email,
            'action': 'update',
            'activation_code': self.activation_code
        })


class AbstractArticle(models.Model):
    """
    An Article within a Message which will be send through a Submission.
    """

    sortorder = models.PositiveIntegerField(
        help_text=_('Sort order determines the order in which articles are '
                    'concatenated in a post.'),
        verbose_name=_('sort order'), blank=True
    )

    title = models.CharField(max_length=200, verbose_name=_('title'))
    text = models.TextField(verbose_name=_('text'))

    url = models.URLField(
        verbose_name=_('link'), blank=True, null=True
    )

    # Make this a foreign key for added elegance
    image = DynamicImageField(
        upload_to='newsletter/images/%Y/%m/%d', blank=True, null=True,
        verbose_name=_('image')
    )

    # Message this article is associated with
    # TODO: Refactor post to message (post is legacy notation).
    post = models.ForeignKey(
        newsletter_settings.MESSAGE_MODEL, verbose_name=_('message'), related_name='articles',
        on_delete=models.CASCADE
    )

    class Meta:
        abstract = True
        ordering = ('sortorder',)
        verbose_name = _('article')
        verbose_name_plural = _('articles')
        unique_together = ('post', 'sortorder')

    def __str__(self):
        return self.title

    def save(self, **kwargs):
        if self.sortorder is None:
            # If saving a new object get the next available Article ordering
            # as to assure uniqueness.
            self.sortorder = self.post.get_next_article_sortorder()

        super().save()


class AbstractAttachment(models.Model):
    """ Attachment for a Message. """

    file = models.FileField(
        upload_to=attachment_upload_to,
        blank=False, null=False,
        verbose_name=_('attachment')
    )

    message = models.ForeignKey(
        newsletter_settings.MESSAGE_MODEL, verbose_name=_('message'), on_delete=models.CASCADE, related_name='attachments',
    )

    class Meta:
        abstract = True
        verbose_name = _('attachment')
        verbose_name_plural = _('attachments')

    def __str__(self):
        return _("%(file_name)s on %(message)s") % {
            'file_name': self.file_name,
            'message': self.message
        }

    @property
    def file_name(self):
        return os.path.split(self.file.name)[1]




class AbstractMessage(models.Model):
    """ Message as sent through a Submission. """

    _Newsletter = None
    @property
    def Newsletter(self):
        if not self._Newsletter:
            self._Newsletter = get_newsletter_model()
        return self._Newsletter

    title = models.CharField(max_length=200, verbose_name=_('title'))
    slug = models.SlugField(verbose_name=_('slug'))

    newsletter = models.ForeignKey(
        newsletter_settings.NEWSLETTER_MODEL, verbose_name=_('newsletter'), on_delete=models.CASCADE, default=get_default_newsletter
    )

    date_create = models.DateTimeField(
        verbose_name=_('created'), auto_now_add=True, editable=False
    )
    date_modify = models.DateTimeField(
        verbose_name=_('modified'), auto_now=True, editable=False
    )

    def __str__(self):
        try:
            return _("%(title)s in %(newsletter)s") % {
                'title': self.title,
                'newsletter': self.newsletter
            }
        except self.Newsletter.DoesNotExist:
            logger.warning('No newsletter has been set for this message yet.')
            return self.title

    class Meta:
        abstract = True
        verbose_name = _('message')
        verbose_name_plural = _('messages')
        unique_together = ('slug', 'newsletter')



    def get_next_article_sortorder(self):
        """ Get next available sortorder for Article. """

        next_order = self.articles.aggregate(
            models.Max('sortorder')
        )['sortorder__max']

        if next_order:
            return next_order + 10
        else:
            return 10

    @cached_property
    def _templates(self):
        """Return a (subject_template, text_template, html_template) tuple."""
        return self.newsletter.get_templates('message')

    @property
    def subject_template(self):
        return self._templates[0]

    @property
    def text_template(self):
        return self._templates[1]

    @property
    def html_template(self):
        return self._templates[2]

    @classmethod
    def get_default(cls):
        try:
            return cls.objects.order_by('-date_create').all()[0]
        except IndexError:
            return None


class AbstractSubmission(models.Model):
    """
    Submission represents a particular Message as it is being submitted
    to a list of Subscribers. This is where actual queueing and submission
    happen.
    """

    _Newsletter = None
    @property
    def Newsletter(self):
        if not self._Newsletter:
            self._Newsletter = get_newsletter_model()
        return self._Newsletter

    _Attachment = None
    @property
    def Attachment(self):
        if not self._Attachment:
            self._Attachment = get_attachment_model()
        return self._Attachment

    newsletter = models.ForeignKey(
        newsletter_settings.NEWSLETTER_MODEL, verbose_name=_('newsletter'), editable=False,
        on_delete=models.CASCADE
    )
    message = models.ForeignKey(
        newsletter_settings.MESSAGE_MODEL, verbose_name=_('message'), editable=True, null=False,
        on_delete=models.CASCADE
    )

    subscriptions = models.ManyToManyField(
        'Subscription',
        help_text=_('If you select none, the system will automatically find '
                    'the subscribers for you.'),
        blank=True, db_index=True, verbose_name=_('recipients'),
        limit_choices_to={'subscribed': True}
    )

    publish_date = models.DateTimeField(
        verbose_name=_('publication date'), blank=True, null=True,
        default=now, db_index=True
    )
    publish = models.BooleanField(
        default=True, verbose_name=_('publish'),
        help_text=_('Publish in archive.'), db_index=True
    )

    prepared = models.BooleanField(
        default=False, verbose_name=_('prepared'),
        db_index=True, editable=False
    )
    sent = models.BooleanField(
        default=False, verbose_name=_('sent'),
        db_index=True, editable=False
    )
    sending = models.BooleanField(
        default=False, verbose_name=_('sending'),
        db_index=True, editable=False
    )

    class Meta:
        abstract = True
        verbose_name = _('submission')
        verbose_name_plural = _('submissions')

    def __str__(self):
        return _("%(newsletter)s on %(publish_date)s") % {
            'newsletter': self.message,
            'publish_date': self.publish_date
        }

    def save(self, **kwargs):
        """ Set the newsletter from associated message upon saving. """
        assert self.message.newsletter

        self.newsletter = self.message.newsletter

        return super().save()

    def get_absolute_url(self):
        assert self.newsletter.slug
        assert self.message.slug

        return reverse(
            'newsletter_archive_detail', kwargs={
                'newsletter_slug': self.newsletter.slug,
                'year': self.publish_date.year,
                'month': self.publish_date.month,
                'day': self.publish_date.day,
                'slug': self.message.slug
            }
        )

    @property
    def status(self):
        if self.sending:
            return _('sending')
        elif self.sent:
            return _('sent')
        elif self.prepared:
            return _('prepared')
        else:
            return _('pending')

    @cached_property
    def extra_headers(self):
        return {
            'List-Unsubscribe': 'http://{}{}'.format(
                Site.objects.get_current().domain,
                reverse('newsletter:newsletter_unsubscribe_request',
                        args=[self.message.newsletter.slug])
            ),
        }

    def submit(self):

        # these are the specific subscriptions in the many to many field
        subscriptions = self.subscriptions.filter(subscribed=True)

        logger.info(f"Submitting {self} to {subscriptions.count()} users")

        assert self.publish_date < now(), \
            'Something smells fishy; submission time in future.'

        self.sending = True
        self.save()

        try:
            for idx, subscription in enumerate(subscriptions, start=1):
                if hasattr(settings, 'NEWSLETTER_EMAIL_DELAY'):
                    time.sleep(settings.NEWSLETTER_EMAIL_DELAY)
                if hasattr(settings, 'NEWSLETTER_BATCH_SIZE') and settings.NEWSLETTER_BATCH_SIZE > 0:
                    if idx % settings.NEWSLETTER_BATCH_SIZE == 0:
                        time.sleep(settings.NEWSLETTER_BATCH_DELAY)
                self.send_message(subscription)
            self.sent = True

        except Exception as e:
            logger.error(f"Error while submitting messages for {self}: {e}")
        finally:
            self.sending = False
            self.save()

    def send_message(self, subscription):
        variable_dict = {
            'subscription': subscription,
            'site': Site.objects.get_current(),
            'submission': self,
            'message': self.message,
            'newsletter': self.newsletter,
            'date': self.publish_date,
            'STATIC_URL': settings.STATIC_URL,
            'MEDIA_URL': settings.MEDIA_URL
        }

        subject = self.message.subject_template.render(
            variable_dict).strip()
        text = self.message.text_template.render(variable_dict)

        message = EmailMultiAlternatives(
            subject, text,
            from_email=self.newsletter.get_sender(),
            to=[subscription.get_recipient()],
            headers=self.extra_headers,
        )

        attachments = self.Attachment.objects.filter(message_id=self.message.id)

        for attachment in attachments:
            message.attach_file(attachment.file.path)

        if self.message.html_template:
            message.attach_alternative(
                self.message.html_template.render(variable_dict),
                "text/html"
            )

        try:
            logger.debug(
                gettext('Submitting message to: %s.'),
                subscription
            )

            message.send()

        except Exception as e:
            # TODO: Test coverage for this branch.
            logger.error(
                gettext('Message %(subscription)s failed '
                        'with error: %(error)s'),
                {'subscription': subscription,
                 'error': e}
            )

    @classmethod
    def submit_queue(cls):
        todo = cls.objects.filter(
            prepared=True, sent=False, sending=False,
            publish_date__lt=now()
        )

        for submission in todo:
            submission.submit()

    @classmethod
    def from_message(cls, message):
        logger.debug(gettext('Submission of message %s'), message)
        submission = cls()
        submission.message = message
        submission.newsletter = message.newsletter
        submission.save()
        try:
            submission.subscriptions.set(message.newsletter.get_subscriptions())
        except AttributeError:  # Django < 1.10
            submission.subscriptions = message.newsletter.get_subscriptions()
        return submission
