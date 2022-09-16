import hashlib
import json

import boto3
import botocore

S3_URL_FORMAT = "https://{bucket}.s3.{region}.amazonaws.com/{key}"
S3_URI_FORMAT = "s3://{bucket}/{key}"

s3 = boto3.resource("s3")


def get_or_create_bucket(name):
    """Gets an S3 bucket with boto3 or creates it if it doesn't exist."""
    try:  # try to create a bucket
        name, response = _create_bucket(name)
    except botocore.exceptions.ClientError as err:
        # error handling from https://github.com/boto/boto3/issues/1195#issuecomment-495842252
        status = err.response["ResponseMetadata"]["HTTPStatusCode"]  # status codes identify particular errors

        if status != 409:
            raise err

    return s3.Bucket(name)


def _create_bucket(name):
    """Creates a bucket with the provided name."""
    session = boto3.session.Session()  # sessions hold on to credentials and config
    current_region = session.region_name  # so we can pull the default region
    bucket_config = {"LocationConstraint": current_region}  # and apply it to the bucket

    bucket_response = s3.create_bucket(Bucket=name, CreateBucketConfiguration=bucket_config)

    return name, bucket_response


def make_key(fileobj, filetype=None):
    """Creates a unique key for the fileobj and optionally append the filetype."""
    identifier = make_identifier(fileobj)
    return identifier if filetype is None else f"{identifier}.{filetype}"


def make_unique_bucket_name(prefix, seed):
    """Creates a unique bucket name from a prefix and a seed."""
    name = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{name}"


def get_url_of(bucket, key=None):
    """Returns the url of a bucket and optionally of an object in that bucket."""
    if not isinstance(bucket, str):
        bucket = bucket.name
    region = _get_region(bucket)
    key = key or ""

    return _format_url(bucket, region, key)


def get_uri_of(bucket, key=None):
    """Returns the s3:// uri of a bucket and optionally of an object in that bucket."""
    if not isinstance(bucket, str):
        bucket = bucket.name
    key = key or ""

    return _format_uri(bucket, key)


def enable_bucket_versioning(bucket):
    """Turns on versioning for bucket contents, which avoids deletion."""
    if not isinstance(bucket, str):
        bucket = bucket.name

    bucket_versioning = s3.BucketVersioning(bucket)
    return bucket_versioning.enable()


def add_access_policy(bucket):
    """Adds a policy to our bucket that allows the Gantry app to access data."""
    access_policy = json.dumps(_get_policy(bucket.name))
    s3.meta.client.put_bucket_policy(Bucket=bucket.name, Policy=access_policy)


def _get_policy(bucket_name):
    """Returns a bucket policy allowing Gantry app access as a JSON-compatible dictionary."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "AWS": [
                        "arn:aws:iam::848836713690:root",
                        "arn:aws:iam::339325199688:root",
                        "arn:aws:iam::665957668247:root",
                    ]
                },
                "Action": ["s3:GetObject", "s3:GetObjectVersion"],
                "Resource": f"arn:aws:s3:::{bucket_name}/*",
            },
            {
                "Effect": "Allow",
                "Principal": {
                    "AWS": [
                        "arn:aws:iam::848836713690:root",
                        "arn:aws:iam::339325199688:root",
                        "arn:aws:iam::665957668247:root",
                    ]
                },
                "Action": "s3:ListBucketVersions",
                "Resource": f"arn:aws:s3:::{bucket_name}",
            },
        ],
    }


def make_identifier(byte_data):
    """Create a unique identifier for a collection of bytes via hashing."""
    # feed them to hashing algo -- security is not critical here, so we use SHA-1
    hashed_data = hashlib.sha1(byte_data)  # noqa: S3
    return hashed_data.hexdigest()


def _get_region(bucket):
    """Determine the region of an s3 bucket."""
    if not isinstance(bucket, str):
        bucket = bucket.name

    s3_client = boto3.client("s3")
    bucket_location_response = s3_client.get_bucket_location(Bucket=bucket)
    return bucket_location_response["LocationConstraint"]


def _format_url(bucket_name, region, key=None):
    key = key or ""
    return S3_URL_FORMAT.format(bucket=bucket_name, region=region, key=key)


def _format_uri(bucket_name, key=None):
    key = key or ""
    return S3_URI_FORMAT.format(bucket=bucket_name, key=key)
