#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🚀 Testing Bedrock Stock Agent Deployment${NC}\n"

# Load environment
if [ -f .env ]; then
    source .env
else
    echo -e "${RED}❌ .env file not found${NC}"
    exit 1
fi

# 1. Test Health Endpoint
echo -e "${YELLOW}1️⃣  Testing Health Endpoint${NC}"
if response=$(curl -s "${API_ENDPOINT}/health"); then
    if echo "$response" | grep -q "healthy"; then
        echo -e "${GREEN}✅ Health check passed${NC}"
        echo "   Response: $response"
    else
        echo -e "${RED}❌ Health check returned unexpected response${NC}"
        echo "   Response: $response"
    fi
else
    echo -e "${RED}❌ Health endpoint unreachable${NC}"
    echo "   Make sure API_ENDPOINT is set correctly in .env"
    exit 1
fi

# 2. Test Cognito Authentication
echo -e "\n${YELLOW}2️⃣  Testing Cognito Authentication${NC}"

# Use AWS CLI to get token
auth_response=$(aws cognito-idp initiate-auth \
    --client-id "$COGNITO_CLIENT_ID" \
    --auth-flow USER_PASSWORD_AUTH \
    --auth-parameters USERNAME="${COGNITO_USERNAME}@example.com" PASSWORD="$COGNITO_PASSWORD" \
    --region "$AWS_REGION" 2>/dev/null)

if [ $? -eq 0 ]; then
    id_token=$(echo "$auth_response" | jq -r '.AuthenticationResult.IdToken')
    if [ -n "$id_token" ] && [ "$id_token" != "null" ]; then
        echo -e "${GREEN}✅ Cognito authentication successful${NC}"
        echo "   Token: ${id_token:0:50}..."
    else
        echo -e "${RED}❌ Failed to extract token${NC}"
        exit 1
    fi
else
    echo -e "${RED}❌ Cognito authentication failed${NC}"
    echo "   Make sure credentials in .env are correct"
    exit 1
fi

# 3. Test Invoke Endpoint (Development - no auth)
echo -e "\n${YELLOW}3️⃣  Testing Invoke Endpoint (Development)${NC}"

response=$(curl -s -X POST "${API_ENDPOINT}/invoke-dev" \
    -H "Content-Type: application/json" \
    -d '{"input": {"prompt": "What is Amazons stock price now?"}}' \
    -w "\n%{http_code}")

http_code=$(echo "$response" | tail -n 1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" = "200" ]; then
    echo -e "${GREEN}✅ Invoke endpoint responded${NC}"

    # Check if streaming newline-delimited JSON
    if echo "$body" | head -n 1 | grep -q "type"; then
        echo "   Response (first event):"
        echo "   $(echo "$body" | head -n 1 | jq -c '.' 2>/dev/null || echo "$body" | head -n 1)"
    fi
else
    echo -e "${RED}❌ Invoke endpoint returned HTTP $http_code${NC}"
    echo "   Response: $body"
fi

# 4. Test Invoke Endpoint with Authentication
echo -e "\n${YELLOW}4️⃣  Testing Authenticated Invoke Endpoint${NC}"

response=$(curl -s -X POST "${API_ENDPOINT}/invoke" \
    -H "Authorization: Bearer $id_token" \
    -H "Content-Type: application/json" \
    -d '{"input": {"prompt": "What is Amazons stock price now?"}}' \
    -w "\n%{http_code}")

http_code=$(echo "$response" | tail -n 1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" = "200" ]; then
    echo -e "${GREEN}✅ Authenticated invoke endpoint responded${NC}"

    # Check if streaming newline-delimited JSON
    if echo "$body" | head -n 1 | grep -q "type"; then
        echo "   Response (first 3 events):"
        echo "$body" | head -n 3 | while read line; do
            echo "   $(echo "$line" | jq -c '.type, (.content | split(" ") | .[0:3] | join(" "))' 2>/dev/null || echo "$line")"
        done
    fi
else
    echo -e "${RED}❌ Authenticated invoke endpoint returned HTTP $http_code${NC}"
    echo "   Response: $body"
fi

echo -e "\n${GREEN}✅ All tests completed!${NC}\n"
echo "📝 Next steps:"
echo "   1. Review logs in CloudWatch: /aws/apigateway/bedrock-stock-agent"
echo "   2. Check README.md for troubleshooting"
