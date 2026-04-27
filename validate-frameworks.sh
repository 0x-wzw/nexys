#!/bin/bash
# Framework Validation Suite
# Tests each component before inclusion in unified platform

set -e

WORKSPACE="/home/ubuntu/.openclaw/workspace"
REPOS_DIR="$WORKSPACE/repos"
RESULTS_DIR="$WORKSPACE/platform-consolidation/validation-results"
mkdir -p "$RESULTS_DIR"

echo "=========================================="
echo "Framework Validation Suite"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Validation results
declare -A RESULTS

validate_repo() {
    local repo_name=$1
    local repo_path=$2
    local category=$3
    
    echo "Validating: $repo_name ($category)"
    echo "----------------------------------------"
    
    local score=0
    local max_score=100
    local report=""
    
    # Test 1: Repository exists and has content
    if [ -d "$repo_path" ] && [ "$(ls -A $repo_path)" ]; then
        echo "  ✓ Repository exists"
        score=$((score + 10))
    else
        echo "  ✗ Repository missing or empty"
        report="Repository not found or empty"
    fi
    
    # Test 2: Has README
    if [ -f "$repo_path/README.md" ] || [ -f "$repo_path/readme.md" ]; then
        echo "  ✓ Documentation present"
        score=$((score + 10))
    else
        echo "  ⚠ No README found"
    fi
    
    # Test 3: Has clear entry point
    if [ -f "$repo_path/main.py" ] || [ -f "$repo_path/index.js" ] || [ -f "$repo_path/src/main.py" ] || [ -f "$repo_path/package.json" ] || [ -f "$repo_path/requirements.txt" ]; then
        echo "  ✓ Entry point identifiable"
        score=$((score + 15))
    else
        echo "  ⚠ Entry point unclear"
    fi
    
    # Test 4: Dependency management
    if [ -f "$repo_path/requirements.txt" ] || [ -f "$repo_path/package.json" ] || [ -f "$repo_path/pyproject.toml" ] || [ -f "$repo_path/Cargo.toml" ]; then
        echo "  ✓ Dependencies declared"
        score=$((score + 15))
    else
        echo "  ⚠ No dependency file found"
    fi
    
    # Test 5: Has tests
    if [ -d "$repo_path/tests" ] || [ -d "$repo_path/test" ] || [ -f "$repo_path/test_*.py" ] || [ -f "$repo_path/*_test.py" ]; then
        echo "  ✓ Tests present"
        score=$((score + 20))
    else
        echo "  ⚠ No tests found"
    fi
    
    # Test 6: Recent activity (within 30 days)
    if [ -d "$repo_path/.git" ]; then
        local last_commit=$(git -C "$repo_path" log -1 --format=%ct 2>/dev/null || echo 0)
        local now=$(date +%s)
        local days_since=$(( (now - last_commit) / 86400 ))
        
        if [ $days_since -lt 30 ]; then
            echo "  ✓ Active development (last commit: ${days_since} days ago)"
            score=$((score + 15))
        else
            echo "  ⚠ Stale (last commit: ${days_since} days ago)"
        fi
    else
        echo "  ⚠ Not a git repository"
    fi
    
    # Test 7: No obvious security issues (basic check)
    if [ -f "$repo_path/.env" ] || [ -f "$repo_path/secrets.txt" ] || grep -r "password" "$repo_path" --include="*.py" --include="*.js" 2>/dev/null | head -1 > /dev/null; then
        echo "  ⚠ Potential security concerns (secrets or hardcoded passwords)"
    else
        echo "  ✓ No obvious security issues"
        score=$((score + 15))
    fi
    
    # Store result
    RESULTS[$repo_name]="$score|$max_score|$category|$report"
    
    echo ""
    echo "  Score: $score/$max_score"
    
    if [ $score -ge 80 ]; then
        echo -e "  ${GREEN}STATUS: APPROVED${NC}"
    elif [ $score -ge 60 ]; then
        echo -e "  ${YELLOW}STATUS: CONDITIONAL${NC}"
    else
        echo -e "  ${RED}STATUS: REJECTED${NC}"
    fi
    
    echo ""
}

# Main validation loop
echo "Starting validation of candidate frameworks..."
echo ""

# Clone or use local copies
cd "$WORKSPACE"

# Validate each framework
validate_repo "necroswarm" "$WORKSPACE/../necroswarm" "workforce"
validate_repo "neuroswarm" "$WORKSPACE/../neuroswarm" "workforce-memory"
validate_repo "obliviarch" "$WORKSPACE/../obliviarch" "memory"
validate_repo "voidtether" "$WORKSPACE/../voidtether" "integration"
validate_repo "openclaw-namespace" "$WORKSPACE/../openclaw-namespace" "workflow"
validate_repo "openclaw-memory-evolution" "$WORKSPACE/../openclaw-memory-evolution" "memory"
validate_repo "openclaw-deterministic-retrieval" "$WORKSPACE/../openclaw-deterministic-retrieval" "workflow"
validate_repo "agent-identity" "$WORKSPACE/../agent-identity" "security"
validate_repo "sentientforge" "$WORKSPACE/../sentientforge" "research"

# Generate report
echo "=========================================="
echo "Validation Summary"
echo "=========================================="
echo ""

APPROVED=()
CONDITIONAL=()
REJECTED=()

for repo in "${!RESULTS[@]}"; do
    IFS='|' read -r score max category report <<< "${RESULTS[$repo]}"
    
    if [ $score -ge 80 ]; then
        APPROVED+=("$repo ($score/$max)")
    elif [ $score -ge 60 ]; then
        CONDITIONAL+=("$repo ($score/$max)")
    else
        REJECTED+=("$repo ($score/$max)")
    fi
done

echo -e "${GREEN}APPROVED (${#APPROVED[@]}):${NC}"
for item in "${APPROVED[@]}"; do
    echo "  ✓ $item"
done

echo ""
echo -e "${YELLOW}CONDITIONAL (${#CONDITIONAL[@]}):${NC}"
for item in "${CONDITIONAL[@]}"; do
    echo "  ⚠ $item"
done

echo ""
echo -e "${RED}REJECTED (${#REJECTED[@]}):${NC}"
for item in "${REJECTED[@]}"; do
    echo "  ✗ $item"
done

echo ""
echo "=========================================="
echo "Recommendations"
echo "=========================================="
echo ""

if [ ${#APPROVED[@]} -ge 4 ]; then
    echo "✓ Sufficient frameworks approved to proceed with consolidation"
    echo "  Priority order:"
    echo "    1. Core infrastructure (VoidTether, Namespace)"
    echo "    2. Memory layer (NeuroSwarm + Obliviarch)"
    echo "    3. Workforce layer (NecroSwarm)"
else
    echo "⚠ More frameworks need validation before consolidation"
    echo "  Focus on improving:"
    for item in "${CONDITIONAL[@]}" "${REJECTED[@]}"; do
        echo "    - $item"
    done
fi

echo ""
echo "Full report saved to: $RESULTS_DIR/validation-report-$(date +%Y%m%d).txt"

# Save detailed report
{
    echo "Framework Validation Report"
    echo "Generated: $(date)"
    echo "=========================================="
    echo ""
    
    for repo in "${!RESULTS[@]}"; do
        IFS='|' read -r score max category report <<< "${RESULTS[$repo]}"
        echo "Repository: $repo"
        echo "Category: $category"
        echo "Score: $score/$max"
        echo "Status: $(if [ $score -ge 80 ]; then echo "APPROVED"; elif [ $score -ge 60 ]; then echo "CONDITIONAL"; else echo "REJECTED"; fi)"
        echo "Notes: $report"
        echo "---"
        echo ""
    done
} > "$RESULTS_DIR/validation-report-$(date +%Y%m%d).txt"

echo ""
echo "Validation complete!"
