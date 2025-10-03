#!/bin/bash

# Agent Scholar - Git Push Script
# This script pushes all completed work to the existing GitHub repository

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Agent Scholar - Pushing Complete Project to GitHub${NC}"
echo -e "${BLUE}Repository: https://github.com/tanDivina/agent-scholar${NC}"
echo ""

# Check if git is initialized
if [ ! -d ".git" ]; then
    echo -e "${RED}❌ Git repository not found. Please run this from the project root.${NC}"
    exit 1
else
    echo -e "${GREEN}✅ Git repository found${NC}"
fi

# Add all files
echo -e "${YELLOW}Adding all files to Git...${NC}"
git add .

# Check if there are any changes to commit
if git diff --staged --quiet; then
    echo -e "${YELLOW}No changes to commit${NC}"
else
    # Commit changes
    echo -e "${YELLOW}Committing changes...${NC}"
    git commit -m "feat: complete Agent Scholar AI research assistant

🧠 Agent Scholar - Next-Generation AI Research Assistant

✨ Features:
- Multi-tool AI coordination (Web Search + Document Analysis + Code Execution)
- Advanced document intelligence with theme extraction and contradiction detection
- Real-time code generation and visualization
- Enterprise-grade security and authentication
- Auto-scaling serverless AWS architecture
- Comprehensive testing and monitoring

🏗️ Architecture:
- Amazon Bedrock Agent with Claude 3 Sonnet
- Custom Action Groups for specialized AI tools
- OpenSearch Serverless for vector search
- Complete AWS serverless infrastructure
- Performance optimization and auto-scaling

📚 Documentation:
- Complete deployment automation
- Comprehensive API documentation
- Demo scenarios and presentation materials
- End-to-end testing framework

🚀 Ready for production deployment and custom frontend integration!"

    echo -e "${GREEN}✅ Changes committed${NC}"
fi

# Check if remote origin exists and set it to the correct repository
if git remote get-url origin >/dev/null 2>&1; then
    CURRENT_URL=$(git remote get-url origin)
    EXPECTED_URL="https://github.com/tanDivina/agent-scholar.git"
    
    if [ "$CURRENT_URL" != "$EXPECTED_URL" ]; then
        echo -e "${YELLOW}Updating remote origin URL...${NC}"
        git remote set-url origin "$EXPECTED_URL"
        echo -e "${GREEN}✅ Remote origin updated to: ${EXPECTED_URL}${NC}"
    else
        echo -e "${GREEN}✅ Remote origin already configured correctly${NC}"
    fi
else
    echo -e "${YELLOW}Adding remote origin...${NC}"
    git remote add origin "https://github.com/tanDivina/agent-scholar.git"
    echo -e "${GREEN}✅ Remote origin added: https://github.com/tanDivina/agent-scholar.git${NC}"
fi

# Check if we're on main branch
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo -e "${YELLOW}Creating and switching to main branch...${NC}"
    git checkout -b main
    echo -e "${GREEN}✅ Switched to main branch${NC}"
fi

# Pull latest changes first to avoid conflicts
echo -e "${YELLOW}Pulling latest changes from GitHub...${NC}"
if git pull origin main --rebase; then
    echo -e "${GREEN}✅ Successfully pulled latest changes${NC}"
else
    echo -e "${YELLOW}⚠️  Pull failed or no remote changes. Continuing...${NC}"
fi

# Push to GitHub
echo -e "${YELLOW}Pushing complete Agent Scholar project to GitHub...${NC}"
if git push origin main; then
    echo -e "${GREEN}✅ Successfully pushed to GitHub!${NC}"
    echo ""
    echo -e "${BLUE}🎉 Complete Agent Scholar project is now on GitHub!${NC}"
    echo -e "${BLUE}Repository: https://github.com/tanDivina/agent-scholar${NC}"
    echo ""
    echo -e "${BLUE}🚀 What's now available on GitHub:${NC}"
    echo -e "✅ Complete codebase with all 16 tasks completed"
    echo -e "✅ Production-ready AWS serverless architecture"
    echo -e "✅ Multi-tool AI coordination system"
    echo -e "✅ Comprehensive documentation and API reference"
    echo -e "✅ Demo scenarios and presentation materials"
    echo -e "✅ Automated deployment scripts"
    echo -e "✅ Complete testing framework (unit, integration, E2E, load)"
    echo -e "✅ Security and authentication system"
    echo -e "✅ Performance optimization and auto-scaling"
    echo -e "✅ Streamlit web interface (basic and secure versions)"
    echo -e "✅ CI/CD pipeline with GitHub Actions"
    echo -e "✅ Issue templates and contributing guidelines"
    echo ""
    echo -e "${BLUE}📚 Key Documentation:${NC}"
    echo -e "• README.md - Project overview and quick start"
    echo -e "• DEPLOYMENT_GUIDE.md - Complete deployment instructions"
    echo -e "• API_DOCUMENTATION.md - Full REST API reference"
    echo -e "• DEMO_SCENARIOS.md - Demo scripts and presentation guide"
    echo -e "• PRESENTATION_SLIDES.md - Ready-to-use presentation materials"
    echo ""
    echo -e "${BLUE}🎯 Ready for:${NC}"
    echo -e "• Production deployment with ./deploy.sh"
    echo -e "• Custom frontend development using the REST API"
    echo -e "• Demos and presentations"
    echo -e "• Further development and customization"
    echo ""
else
    echo -e "${RED}❌ Push failed. This might be because:${NC}"
    echo -e "1. Authentication is required (GitHub username/password or token)"
    echo -e "2. You don't have push permissions to the repository"
    echo -e "3. There are merge conflicts that need to be resolved"
    echo ""
    echo -e "${BLUE}💡 Solutions:${NC}"
    echo -e "1. Set up authentication:"
    echo -e "   • SSH keys: https://docs.github.com/en/authentication/connecting-to-github-with-ssh"
    echo -e "   • Personal access token: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token"
    echo ""
    echo -e "2. Check repository permissions on GitHub"
    echo ""
    echo -e "3. If there are conflicts, resolve them manually:"
    echo -e "   git status"
    echo -e "   git add ."
    echo -e "   git commit -m 'resolve conflicts'"
    echo -e "   git push origin main"
fi

echo ""
echo -e "${GREEN}🎯 Agent Scholar Git Setup Complete!${NC}"