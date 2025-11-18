#!/usr/bin/env python3
"""
Interactive Test Harness for TimerMind

This harness simulates browser interaction with TimerMind's chat interface,
executing test cases step-by-step with optional pauses for manual review.
Uses an LLM to evaluate whether responses meet expectations.
"""

import json
import sys
import time
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime
import os
from pathlib import Path

# Add parent directory to path to import from main
sys.path.insert(0, str(Path(__file__).parent.parent))

# For LLM evaluation
try:
    import google.generativeai as genai
    from dotenv import load_dotenv
    load_dotenv()
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
except ImportError:
    print("Warning: google-generativeai not available. LLM evaluation disabled.")
    genai = None


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class TimerMindTester:
    """Interactive test harness for TimerMind"""

    def __init__(self, base_url: str = "http://127.0.0.1:8000", interactive: bool = True):
        self.base_url = base_url
        self.interactive = interactive
        self.session_id = None
        self.test_results = []
        self.llm_evaluator = self._init_llm_evaluator()

    def _init_llm_evaluator(self):
        """Initialize LLM for response evaluation"""
        if genai is None:
            return None
        try:
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            return model
        except Exception as e:
            print(f"{Colors.WARNING}Warning: Could not initialize LLM evaluator: {e}{Colors.ENDC}")
            return None

    def load_test_cases(self, filepath: str) -> List[Dict]:
        """Load test cases from JSON file"""
        with open(filepath, 'r') as f:
            return json.load(f)

    def print_banner(self, text: str, color: str = Colors.HEADER):
        """Print a formatted banner"""
        print(f"\n{color}{'=' * 80}")
        print(f"  {text}")
        print(f"{'=' * 80}{Colors.ENDC}\n")

    def print_step(self, step_num: int, total_steps: int, description: str):
        """Print step information"""
        print(f"\n{Colors.BOLD}[Step {step_num}/{total_steps}] {description}{Colors.ENDC}")

    def wait_for_user(self):
        """Pause and wait for user to press Enter"""
        if self.interactive:
            input(f"{Colors.OKCYAN}Press Enter to continue...{Colors.ENDC}")

    def send_message(self, message: str) -> Dict:
        """Send a message to TimerMind API (simulates typing in browser)"""
        print(f"{Colors.OKBLUE}💬 User: {message}{Colors.ENDC}")

        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "message": message,
                "session_id": self.session_id
            }
        )

        if response.status_code == 200:
            data = response.json()
            self.session_id = data.get('session_id')

            print(f"{Colors.OKGREEN}🤖 TimerMind: {data.get('response', 'No response')}{Colors.ENDC}")

            # Show execution trace if available
            if data.get('execution_trace'):
                print(f"{Colors.OKCYAN}   Execution trace: {len(data['execution_trace'])} events{Colors.ENDC}")

            return data
        else:
            error_msg = response.json().get('detail', 'Unknown error')
            print(f"{Colors.FAIL}❌ Error: {error_msg}{Colors.ENDC}")
            return {"error": error_msg}

    def get_timers(self) -> List[Dict]:
        """Fetch current timers from API"""
        response = requests.get(f"{self.base_url}/api/timers")
        if response.status_code == 200:
            return response.json().get('timers', [])
        return []

    def get_preferences(self) -> Dict:
        """Fetch current preferences from API"""
        response = requests.get(f"{self.base_url}/api/preferences")
        if response.status_code == 200:
            return response.json().get('preferences', {})
        return {}

    def reset_data(self):
        """Reset all timers and preferences"""
        print(f"{Colors.WARNING}🧹 Resetting all data...{Colors.ENDC}")
        response = requests.post(f"{self.base_url}/api/reset")
        self.session_id = None
        return response.status_code == 200

    def evaluate_with_llm(self, step: Dict, actual_data: Dict) -> Dict:
        """Use LLM to evaluate if actual data meets expectations"""
        if self.llm_evaluator is None:
            return {"pass": None, "reason": "LLM evaluator not available"}

        expected = step.get('expected_behavior', {})

        prompt = f"""You are a test evaluator for TimerMind, an AI-powered task management system.

Test Step Action: {step.get('action')}
Message Sent: {step.get('message', 'N/A')}

Expected Behavior:
{json.dumps(expected, indent=2)}

Actual Response Data:
{json.dumps(actual_data, indent=2)}

Please evaluate whether the actual response meets the expected behavior.
Consider:
1. Were the expected actions performed (e.g., timer created, preferences updated)?
2. Do the values fall within expected ranges?
3. Does the rationale mention expected concepts?
4. Is the overall behavior correct?

Respond with a JSON object containing:
{{
  "pass": true/false,
  "reason": "Explanation of why the test passed or failed",
  "details": {{
    "matches": ["list of expectations that were met"],
    "mismatches": ["list of expectations that were not met"]
  }}
}}
"""

        try:
            result = self.llm_evaluator.generate_content(prompt)
            response_text = result.text.strip()

            # Extract JSON from markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            evaluation = json.loads(response_text)
            return evaluation
        except Exception as e:
            return {
                "pass": None,
                "reason": f"LLM evaluation failed: {str(e)}",
                "details": {"error": str(e)}
            }

    def verify_expectations(self, step: Dict, timers: List[Dict], preferences: Dict) -> Dict:
        """Verify that actual state matches expected behavior"""
        expected = step.get('expected_behavior', {})
        results = {
            "checks": [],
            "pass": True
        }

        # Check timer creation
        if expected.get('creates_timer'):
            if len(timers) > 0:
                results["checks"].append(("Timer created", True, "✓"))

                # Check timer properties
                latest_timer = timers[0] if timers else {}

                # Check label
                if 'timer_label_contains' in expected:
                    contains = expected['timer_label_contains']
                    if isinstance(contains, str):
                        contains = [contains]
                    label = latest_timer.get('label', '').lower()
                    matches = any(term.lower() in label for term in contains)
                    results["checks"].append((f"Label contains {contains}", matches, "✓" if matches else "✗"))
                    if not matches:
                        results["pass"] = False

                # Check deadline
                if expected.get('has_deadline'):
                    has_deadline = latest_timer.get('deadline') is not None
                    results["checks"].append(("Has deadline", has_deadline, "✓" if has_deadline else "✗"))
                    if not has_deadline:
                        results["pass"] = False

                # Check urgency score range
                if 'urgency_score_range' in expected:
                    min_val, max_val = expected['urgency_score_range']
                    urgency = latest_timer.get('urgency_score', 0)
                    in_range = min_val <= urgency <= max_val
                    results["checks"].append((
                        f"Urgency score {urgency:.2f} in [{min_val}, {max_val}]",
                        in_range,
                        "✓" if in_range else "✗"
                    ))
                    if not in_range:
                        results["pass"] = False

                # Check importance score range
                if 'importance_score_range' in expected:
                    min_val, max_val = expected['importance_score_range']
                    importance = latest_timer.get('importance_score', 0)
                    in_range = min_val <= importance <= max_val
                    results["checks"].append((
                        f"Importance score {importance:.2f} in [{min_val}, {max_val}]",
                        in_range,
                        "✓" if in_range else "✗"
                    ))
                    if not in_range:
                        results["pass"] = False

                # Check rationale mentions
                if 'rationale_mentions' in expected:
                    rationale = latest_timer.get('rationale', '').lower()
                    for keyword in expected['rationale_mentions']:
                        mentioned = keyword.lower() in rationale
                        results["checks"].append((
                            f"Rationale mentions '{keyword}'",
                            mentioned,
                            "✓" if mentioned else "✗"
                        ))
                        if not mentioned:
                            results["pass"] = False

                # Check rationale exists (regression test for Why button)
                if expected.get('has_rationale'):
                    has_rationale = latest_timer.get('rationale') is not None
                    results["checks"].append((
                        "Has rationale",
                        has_rationale,
                        "✓" if has_rationale else "✗"
                    ))
                    if not has_rationale:
                        results["pass"] = False

                # Check rationale is a string
                if expected.get('rationale_is_string'):
                    rationale = latest_timer.get('rationale')
                    is_string = isinstance(rationale, str)
                    results["checks"].append((
                        "Rationale is string",
                        is_string,
                        "✓" if is_string else "✗"
                    ))
                    if not is_string:
                        results["pass"] = False

                # Check rationale is not empty
                if expected.get('rationale_not_empty'):
                    rationale = latest_timer.get('rationale', '')
                    not_empty = len(rationale.strip()) > 0
                    results["checks"].append((
                        "Rationale not empty",
                        not_empty,
                        "✓" if not_empty else "✗"
                    ))
                    if not not_empty:
                        results["pass"] = False
            else:
                results["checks"].append(("Timer created", False, "✗"))
                results["pass"] = False

        # Check timer count
        if 'timer_count' in expected:
            count_match = len(timers) == expected['timer_count']
            results["checks"].append((
                f"Timer count is {expected['timer_count']}",
                count_match,
                "✓" if count_match else "✗"
            ))
            if not count_match:
                results["pass"] = False

        return results

    def run_test_case(self, test_case: Dict) -> Dict:
        """Execute a single test case"""
        test_id = test_case['id']
        test_name = test_case['name']

        self.print_banner(f"Test: {test_name} ({test_id})")
        print(f"Description: {test_case['description']}\n")

        # Reset data before test
        cleanup = test_case.get('cleanup', {})
        if cleanup.get('reset_data'):
            self.reset_data()

        steps = test_case['steps']
        step_results = []

        for i, step in enumerate(steps, 1):
            self.print_step(i, len(steps), step.get('action', 'unknown'))

            action = step.get('action')

            if action == 'send_message':
                # Send message and get response
                response_data = self.send_message(step['message'])

                # Wait for user if interactive
                if self.interactive and i < len(steps):
                    self.wait_for_user()

                # Fetch current state
                timers = self.get_timers()
                preferences = self.get_preferences()

                # Show current state
                print(f"\n{Colors.OKCYAN}📊 Current State:{Colors.ENDC}")
                print(f"   Timers: {len(timers)}")
                if timers:
                    for timer in timers[:3]:  # Show first 3
                        print(f"      - {timer.get('label')} (Priority: {timer.get('priority_score', 0):.2f})")

                # Verify expectations
                verification = self.verify_expectations(step, timers, preferences)

                # LLM evaluation
                llm_eval = self.evaluate_with_llm(step, {
                    "response": response_data,
                    "timers": timers,
                    "preferences": preferences
                })

                # Display verification results
                print(f"\n{Colors.BOLD}Verification Results:{Colors.ENDC}")
                for check_name, passed, symbol in verification["checks"]:
                    color = Colors.OKGREEN if passed else Colors.FAIL
                    print(f"   {color}{symbol} {check_name}{Colors.ENDC}")

                if llm_eval["pass"] is not None:
                    print(f"\n{Colors.BOLD}LLM Evaluation:{Colors.ENDC}")
                    eval_color = Colors.OKGREEN if llm_eval["pass"] else Colors.FAIL
                    print(f"   {eval_color}{'PASS' if llm_eval['pass'] else 'FAIL'}{Colors.ENDC}")
                    print(f"   Reason: {llm_eval['reason']}")

                step_results.append({
                    "step": i,
                    "action": action,
                    "verification": verification,
                    "llm_evaluation": llm_eval
                })

            elif action == 'verify_ordering':
                timers = self.get_timers()
                # TODO: Implement ordering verification
                print(f"{Colors.WARNING}Ordering verification not yet implemented{Colors.ENDC}")

        # Cleanup
        if cleanup.get('reset_data'):
            print(f"\n{Colors.OKCYAN}Cleaning up...{Colors.ENDC}")
            self.reset_data()

        # Overall test result
        overall_pass = all(
            result['verification']['pass'] and
            (result['llm_evaluation']['pass'] if result['llm_evaluation']['pass'] is not None else True)
            for result in step_results
        )

        result_color = Colors.OKGREEN if overall_pass else Colors.FAIL
        print(f"\n{result_color}{'=' * 80}")
        print(f"  Test Result: {'PASS ✓' if overall_pass else 'FAIL ✗'}")
        print(f"{'=' * 80}{Colors.ENDC}\n")

        return {
            "test_id": test_id,
            "test_name": test_name,
            "pass": overall_pass,
            "step_results": step_results,
            "timestamp": datetime.now().isoformat()
        }

    def run_all_tests(self, test_cases: List[Dict]) -> Dict:
        """Execute all test cases"""
        self.print_banner("TimerMind Test Suite", Colors.HEADER)
        print(f"Running {len(test_cases)} test case(s)")
        print(f"Mode: {'Interactive' if self.interactive else 'Automated'}")
        print(f"Base URL: {self.base_url}\n")

        all_results = []

        for test_case in test_cases:
            result = self.run_test_case(test_case)
            all_results.append(result)

            if self.interactive and test_case != test_cases[-1]:
                print(f"\n{Colors.OKCYAN}Next test case ready...{Colors.ENDC}")
                self.wait_for_user()

        # Summary
        passed = sum(1 for r in all_results if r['pass'])
        failed = len(all_results) - passed

        self.print_banner("Test Suite Summary", Colors.HEADER)
        print(f"Total Tests: {len(all_results)}")
        print(f"{Colors.OKGREEN}Passed: {passed}{Colors.ENDC}")
        print(f"{Colors.FAIL}Failed: {failed}{Colors.ENDC}")
        print(f"Pass Rate: {(passed / len(all_results) * 100):.1f}%\n")

        # Save results
        results_file = Path(__file__).parent / f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump({
                "summary": {
                    "total": len(all_results),
                    "passed": passed,
                    "failed": failed,
                    "timestamp": datetime.now().isoformat()
                },
                "results": all_results
            }, f, indent=2)

        print(f"Results saved to: {results_file}")

        return {
            "total": len(all_results),
            "passed": passed,
            "failed": failed,
            "results": all_results
        }


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="TimerMind Interactive Test Harness")
    parser.add_argument('--test-file', default='test_cases.json', help='Path to test cases JSON file')
    parser.add_argument('--base-url', default='http://127.0.0.1:8000', help='TimerMind API base URL')
    parser.add_argument('--auto', action='store_true', help='Run in automated mode (no pauses)')
    parser.add_argument('--test-id', help='Run only a specific test case by ID')

    args = parser.parse_args()

    # Load test cases
    test_file = Path(__file__).parent / args.test_file
    tester = TimerMindTester(base_url=args.base_url, interactive=not args.auto)
    test_cases = tester.load_test_cases(str(test_file))

    # Filter by test ID if specified
    if args.test_id:
        test_cases = [tc for tc in test_cases if tc['id'] == args.test_id]
        if not test_cases:
            print(f"{Colors.FAIL}Error: Test case '{args.test_id}' not found{Colors.ENDC}")
            sys.exit(1)

    # Run tests
    try:
        results = tester.run_all_tests(test_cases)
        sys.exit(0 if results['failed'] == 0 else 1)
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}Tests interrupted by user{Colors.ENDC}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.FAIL}Error running tests: {e}{Colors.ENDC}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
