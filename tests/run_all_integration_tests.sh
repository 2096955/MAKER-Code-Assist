#!/bin/bash
# Run all integration tests
# Requires: All services running

set -e

echo "=========================================="
echo "Full Integration Test Suite"
echo "=========================================="
echo ""
echo "This will test Phase 1 and Phase 2 with real services."
echo "Estimated time: ~2 hours"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  exit 1
fi

# Run test suites
echo ""
echo "Running Test Suite 1: Phase 1..."
bash tests/integration_test_suite_1.sh

echo ""
echo "Running Test Suite 2: Phase 2..."
bash tests/integration_test_suite_2.sh

echo ""
echo "=========================================="
echo "All Integration Tests Complete"
echo "=========================================="
echo ""
echo "Review the output above for any failures."
echo "Check workspace/ for progress files."
echo "Check Redis for task states and skill usage."
echo ""

