from django.db import models


class Verification(models.Model):
    timestamp = models.DateTimeField()
    passed = models.BooleanField()
    message = models.CharField(max_length=200, null=True)
    first_name = models.CharField(max_length=50, null=True)
    last_name = models.CharField(max_length=50, null=True)
    gender = models.CharField(max_length=10, null=True)
    document_expiration_date = models.DateField(null=True)
