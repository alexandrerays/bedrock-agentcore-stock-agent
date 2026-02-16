# S3 bucket for storing financial documents

resource "aws_s3_bucket" "documents" {
  bucket = "${var.app_name}-documents-${data.aws_caller_identity.current.account_id}"

  tags = var.tags
}

# Block public access
resource "aws_s3_bucket_public_access_block" "documents" {
  bucket = aws_s3_bucket.documents.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Versioning
resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Upload documents from local data directory
resource "aws_s3_object" "documents" {
  for_each = fileset("${path.module}/../data", "*.pdf")

  bucket = aws_s3_bucket.documents.id
  key    = "financial-documents/${each.value}"
  source = "${path.module}/../data/${each.value}"

  etag = filemd5("${path.module}/../data/${each.value}")

  tags = var.tags
}

# Get current AWS account ID for bucket naming
data "aws_caller_identity" "current" {}

output "documents_bucket_name" {
  description = "S3 bucket name for documents"
  value       = aws_s3_bucket.documents.id
}

output "documents_bucket_arn" {
  description = "S3 bucket ARN"
  value       = aws_s3_bucket.documents.arn
}

output "documents_bucket_region" {
  description = "S3 bucket region"
  value       = aws_s3_bucket.documents.region
}
