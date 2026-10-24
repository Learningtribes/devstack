"""Classify real botocore SES errors without contacting external services."""
from botocore.exceptions import ClientError
from bulk_email.tasks import _ses_error_policy
cases = [
 ('Throttling', 'Maximum sending rate exceeded', 400, 'infinite'),
 ('ThrottlingException', 'Daily message quota exceeded', 400, 'bulk'),
 ('InvalidParameterValue', 'Illegal address', 400, 'single'),
 ('InvalidParameterValue', 'Invalid content', 400, 'bulk'),
 ('MessageRejected', 'Email identity is not verified', 400, 'bulk'),
 ('ServiceUnavailable', 'Unavailable', 503, 'limited'),
 ('AccessDenied', 'Denied', 403, 'bulk'),
]
for code, message, status, expected in cases:
 error=ClientError({'Error':{'Code':code,'Message':message},'ResponseMetadata':{'HTTPStatusCode':status}}, 'SendRawEmail')
 assert _ses_error_policy(error)==expected, code
print('PASS: 7 real botocore SES classifications, retry versus permanent/recipient failures')
