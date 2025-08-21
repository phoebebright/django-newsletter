Backend Functionlity
======================

Creating a newsletter
-----------------------

    obj = Newsletter.objects.create(title=self.name,
        slug=f"event_newsletter_{self.ref}",
        email=self.manager.email,
        sender="Event Organiser")

Auto Subscribe users to a newsletter
-----------------


    # Assuming you have a user instance
    user = request.user

    # Get the newsletter instance
    newsletter = Newsletter.objects.get(slug="event_newsletter_123")

    # Auto subscribe the user to the newsletter
    auto_subscribe(user, newsletter)


Sending newsletter to all subscribers
----------------------


    # Get the newsletter instance
    newsletter = Newsletter.objects.get(slug="event_newsletter_123")

    # Create a submission for the newsletter
    submission = Submission.objects.create(newsletter=newsletter,
                                           content="This is the content of the newsletter.")

    # Send the newsletter to all subscribers
    submission.send_to_subscribers()
