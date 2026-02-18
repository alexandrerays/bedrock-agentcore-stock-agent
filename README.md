# Bedrock Stock Agent

An AI agent solution on AWS that hosts a FastAPI endpoint for querying real-time and historical stock prices, powered by LangGraph and Bedrock Claude models with Cognito authentication.

## Features

- **ReAct Agent**: LangGraph-based agent using Claude 3.5 Haiku via AWS Bedrock
- **Real-time Stock Prices**: Query current stock prices via yfinance
- **Historical Data**: Retrieve historical stock price trends
- **Document RAG**: Search Amazon financial documents (Annual Report, Earnings Releases)
- **Streaming Responses**: Stream agent reasoning and tool calls via Server-Sent Events
- **Cognito Authentication**: JWT-based authentication via AWS Cognito
- **AWS Deployment**: Dockerized application deployed via Bedrock Agentcore

## Architecture

```
FastAPI Application (Docker Container on Agentcore)
    ├── LangGraph ReAct Agent
    │   ├── Stock Price Tools (yfinance)
    │   └── Document Retrieval (FAISS + RAG)
    ├── Cognito JWT Authentication
    └── Streaming API Endpoint (Server-Sent Events)

AWS Infrastructure (Terraform)        AWS Console
    ├── Cognito User Pool (auth)       ├── Bedrock Agentcore (runtime)
    ├── S3 Bucket (documents)          └── ECR (Docker image)
    ├── IAM Role (permissions)
    └── Bedrock (model inference)
```

## Prerequisites

- AWS Account with permissions to:
  - Access Bedrock models
  - Create Cognito user pools
  - Push images to ECR
  - Create Agentcore runtimes
- Terraform >= 1.0
- Python 3.11+
- Docker

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository>
cd bedrock-stock-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your actual values
```

### 2. Local Development

#### Run FastAPI Locally

```bash
export ENVIRONMENT=dev
export SKIP_AUTH=true

uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Test health
curl http://localhost:8000/ping

# Test invoke (no auth in dev mode)
curl -X POST http://localhost:8000/invocations \
  -H "Content-Type: application/json" \
  -d '{"input": {"prompt": "What is the stock price for Amazon right now?"}}'
```

### 3. Deploy to AWS

#### Infrastructure (Terraform)

Terraform manages the supporting infrastructure: Cognito, S3, and IAM.

```bash
cd terraform

terraform init
terraform plan
terraform apply
terraform output -json
```

#### Agentcore Runtime (Console)

The Agentcore runtime is configured via the AWS console:

1. Build and push Docker image to ECR
2. Create an Agentcore runtime pointing to the ECR image
3. Configure environment variables from `terraform output`:
   - `COGNITO_USER_POOL_ID`
   - `COGNITO_CLIENT_ID`
   - `AWS_REGION`

### 4. Test the Deployment

Open `test_agent.ipynb` and run the cells. The notebook reads credentials from `.env` and tests:

1. Cognito authentication
2. Health check
3. Agent invocation with sample queries

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/ping` | No | Health check |
| POST | `/invoke` | Cognito JWT | Authenticated agent invocation |
| POST | `/invoke-dev` | No (requires `SKIP_AUTH=true`) | Development agent invocation |
| POST | `/invocations` | No | Bedrock Agentcore standard endpoint |

Request body for invoke endpoints:
```json
{
  "input": {
    "prompt": "What is the stock price for Amazon right now?"
  }
}
```

Response: streaming newline-delimited JSON events.

## Project Structure

```
bedrock-stock-agent/
├── src/
│   ├── agent/
│   │   ├── graph.py              # LangGraph ReAct agent
│   │   └── tools.py              # Stock and retrieval tools
│   ├── api/
│   │   ├── main.py               # FastAPI application
│   │   └── auth.py               # Cognito authentication
│   └── knowledge/
│       ├── loader.py             # Document loading
│       └── retriever.py          # FAISS vector store
├── terraform/
│   ├── main.tf                   # Provider and backend
│   ├── cognito.tf                # Cognito resources
│   ├── iam.tf                    # IAM roles and policies
│   ├── s3.tf                     # S3 document storage
│   ├── agentcore.tf              # ECR image output
│   ├── variables.tf              # Input variables
│   └── outputs.tf                # Output values
├── data/                          # Amazon financial documents
├── scripts/                       # Utility scripts
├── test_agent.ipynb               # Test notebook
├── Dockerfile                     # Container definition
├── requirements.txt               # Python dependencies
└── .env.example                   # Environment variable template
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and fill in values:

```bash
AWS_REGION=us-east-1
ENVIRONMENT=dev
COGNITO_USER_POOL_ID=<from terraform output>
COGNITO_CLIENT_ID=<from terraform output>
COGNITO_USERNAME=<your cognito username>
COGNITO_PASSWORD=<your cognito password>
API_ENDPOINT=<your agentcore endpoint>
BEDROCK_MODEL_ID=us.anthropic.claude-3-5-haiku-20241022-v1:0
```

For local development, set `SKIP_AUTH=true` to bypass Cognito authentication.

## Troubleshooting

### Agent not responding
- Check AWS credentials: `aws sts get-caller-identity`
- Verify Bedrock access: `aws bedrock list-foundation-models --region us-east-1`

### Documents not loading
- Verify files in `data/` directory
- Check S3 bucket permissions
- Rebuild vector store: `rm -rf .vector_store`

### Cognito authentication failing
- Verify user exists: `aws cognito-idp admin-get-user --user-pool-id <ID> --username <user>`
- Check token validity (tokens expire after 1 hour)
- Verify client ID matches `.env`

## Cleanup

```bash
cd terraform
terraform destroy
```

## License

MIT
