"""
E2E Test Runner for RedBarSushiAI.

This module runs end-to-end conversation tests against the complete system,
simulating real user interactions through the WebSocket interface.
"""

import asyncio
import json
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import os

import websockets
import httpx
from urllib.parse import urljoin

from app.config import settings
from tests.e2e.conversation_scenarios import (
    ConversationScenario, ConversationTurn, ScenarioType,
    get_all_scenarios, get_scenarios_by_type
)

logger = logging.getLogger(__name__)


@dataclass
class TurnResult:
    """Result of a single conversation turn."""
    turn_number: int
    speaker: str
    message: str
    response: str
    response_time: float
    state: Optional[str] = None
    agent: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    passed: bool = True
    error: Optional[str] = None


@dataclass
class ScenarioResult:
    """Result of running a complete scenario."""
    scenario_id: str
    scenario_name: str
    started_at: datetime
    completed_at: datetime
    total_duration: float
    turns_completed: int
    turns_total: int
    passed: bool
    turn_results: List[TurnResult]
    final_state: Optional[str] = None
    final_context: Optional[Dict[str, Any]] = None
    errors: List[str] = None
    outcome_validation: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class E2ETestRunner:
    """Runs E2E conversation tests."""
    
    def __init__(self, base_url: str = None, ws_url: str = None):
        """Initialize test runner with endpoints."""
        self.base_url = base_url or f"http://localhost:{settings.PORT}"
        self.ws_url = ws_url or f"ws://localhost:{settings.PORT}/ws"
        self.http_client = httpx.AsyncClient(base_url=self.base_url)
        self.results: List[ScenarioResult] = []
    
    async def setup(self):
        """Set up test environment."""
        # Verify system is running
        try:
            response = await self.http_client.get("/health")
            if response.status_code != 200:
                raise Exception(f"Health check failed: {response.status_code}")
            logger.info("System health check passed")
        except Exception as e:
            logger.error(f"Failed to connect to system: {e}")
            raise
    
    async def teardown(self):
        """Clean up test environment."""
        await self.http_client.aclose()
    
    async def run_scenario(self, scenario: ConversationScenario) -> ScenarioResult:
        """Run a single conversation scenario."""
        logger.info(f"Running scenario: {scenario.name}")
        
        started_at = datetime.now()
        turn_results = []
        errors = []
        
        # Initialize WebSocket connection
        session_id = f"e2e_test_{scenario.id}_{int(time.time())}"
        
        try:
            async with websockets.connect(
                f"{self.ws_url}/{session_id}",
                ping_interval=10,
                ping_timeout=5
            ) as websocket:
                
                # Initialize conversation
                await self._initialize_conversation(websocket, scenario)
                
                # Run each turn
                for i, turn in enumerate(scenario.turns):
                    logger.info(f"Turn {i+1}/{len(scenario.turns)}: {turn.speaker}")
                    
                    try:
                        result = await self._execute_turn(
                            websocket, turn, i + 1, scenario
                        )
                        turn_results.append(result)
                        
                        if not result.passed:
                            errors.append(f"Turn {i+1} failed: {result.error}")
                            
                        # Wait before next turn
                        await asyncio.sleep(turn.wait_time)
                        
                    except Exception as e:
                        logger.error(f"Error in turn {i+1}: {e}")
                        errors.append(f"Turn {i+1} error: {str(e)}")
                        turn_results.append(TurnResult(
                            turn_number=i + 1,
                            speaker=turn.speaker,
                            message=turn.message,
                            response="",
                            response_time=0,
                            passed=False,
                            error=str(e)
                        ))
                        
                        # Decide whether to continue
                        if i < len(scenario.turns) - 1:
                            logger.info("Attempting to continue after error...")
                        else:
                            break
                
                # Get final state
                final_state, final_context = await self._get_conversation_state(
                    session_id
                )
                
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            errors.append(f"WebSocket connection error: {str(e)}")
            final_state = None
            final_context = None
        
        completed_at = datetime.now()
        total_duration = (completed_at - started_at).total_seconds()
        
        # Validate outcome
        outcome_validation = None
        if scenario.expected_outcome and final_context:
            outcome_validation = self._validate_outcome(
                scenario.expected_outcome,
                final_context,
                turn_results
            )
        
        # Determine if scenario passed
        passed = (
            len(errors) == 0 and
            all(tr.passed for tr in turn_results) and
            (outcome_validation is None or outcome_validation.get("passed", False))
        )
        
        return ScenarioResult(
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            started_at=started_at,
            completed_at=completed_at,
            total_duration=total_duration,
            turns_completed=len(turn_results),
            turns_total=len(scenario.turns),
            passed=passed,
            turn_results=turn_results,
            final_state=final_state,
            final_context=final_context,
            errors=errors,
            outcome_validation=outcome_validation
        )
    
    async def _initialize_conversation(
        self,
        websocket,
        scenario: ConversationScenario
    ):
        """Initialize conversation with any required context."""
        if scenario.initial_context:
            init_message = {
                "type": "init",
                "context": scenario.initial_context
            }
            await websocket.send(json.dumps(init_message))
            
            # Wait for acknowledgment
            response = await websocket.recv()
            logger.debug(f"Init response: {response}")
    
    async def _execute_turn(
        self,
        websocket,
        turn: ConversationTurn,
        turn_number: int,
        scenario: ConversationScenario
    ) -> TurnResult:
        """Execute a single conversation turn."""
        start_time = time.time()
        
        if turn.speaker == "user":
            # Send user message
            message = {
                "type": "user_message",
                "text": turn.message
            }
            await websocket.send(json.dumps(message))
            
            # Collect response
            response_text = ""
            response_data = {}
            
            # Wait for complete response
            while True:
                try:
                    response = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=30.0
                    )
                    data = json.loads(response)
                    
                    if data.get("type") == "response":
                        response_text = data.get("text", "")
                        response_data = data
                        break
                    elif data.get("type") == "chunk":
                        # Handle streaming response
                        response_text += data.get("text", "")
                    elif data.get("type") == "error":
                        raise Exception(f"System error: {data.get('message')}")
                        
                except asyncio.TimeoutError:
                    raise Exception("Response timeout")
            
            response_time = time.time() - start_time
            
            # Validate response
            passed = True
            error = None
            
            # Check expected state
            if turn.expected_state and response_data.get("state") != turn.expected_state:
                passed = False
                error = f"Expected state {turn.expected_state}, got {response_data.get('state')}"
            
            # Check expected agent
            if turn.expected_agent and response_data.get("agent") != turn.expected_agent:
                passed = False
                error = f"Expected agent {turn.expected_agent}, got {response_data.get('agent')}"
            
            # Check expected context
            if turn.expected_context:
                context = response_data.get("context", {})
                if callable(turn.expected_context):
                    if not turn.expected_context(context):
                        passed = False
                        error = "Context validation function returned False"
                else:
                    for key, expected_value in turn.expected_context.items():
                        if context.get(key) != expected_value:
                            passed = False
                            error = f"Expected context[{key}]={expected_value}, got {context.get(key)}"
            
            # Check validation function
            if turn.validation_function and not turn.validation_function(response_text):
                passed = False
                error = "Response validation function returned False"
            
            return TurnResult(
                turn_number=turn_number,
                speaker=turn.speaker,
                message=turn.message,
                response=response_text,
                response_time=response_time,
                state=response_data.get("state"),
                agent=response_data.get("agent"),
                context=response_data.get("context"),
                passed=passed,
                error=error
            )
            
        else:  # system turn
            # System turns are typically just for initial state
            return TurnResult(
                turn_number=turn_number,
                speaker=turn.speaker,
                message=turn.message,
                response="[System Ready]",
                response_time=0,
                state=turn.expected_state,
                agent=turn.expected_agent,
                passed=True
            )
    
    async def _get_conversation_state(
        self,
        session_id: str
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Get current conversation state via HTTP API."""
        try:
            response = await self.http_client.get(
                f"/conversation/{session_id}/state"
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("state"), data.get("context")
        except Exception as e:
            logger.error(f"Failed to get conversation state: {e}")
        
        return None, None
    
    def _validate_outcome(
        self,
        expected: Dict[str, Any],
        context: Dict[str, Any],
        turn_results: List[TurnResult]
    ) -> Dict[str, Any]:
        """Validate expected outcome against actual results."""
        validations = {}
        all_passed = True
        
        for key, expected_value in expected.items():
            actual_value = None
            
            # Special handling for certain keys
            if key == "order_placed":
                actual_value = context.get("order_id") is not None
            elif key == "order_type":
                actual_value = context.get("order_type")
            elif key == "items_count":
                cart = context.get("cart", [])
                actual_value = len(cart)
            elif key == "global_commands_used":
                # Check turn results for global command usage
                commands_used = []
                for tr in turn_results:
                    if tr.context and tr.context.get("global_command"):
                        commands_used.append(tr.context["global_command"])
                actual_value = commands_used
            else:
                actual_value = context.get(key)
            
            passed = actual_value == expected_value
            validations[key] = {
                "expected": expected_value,
                "actual": actual_value,
                "passed": passed
            }
            
            if not passed:
                all_passed = False
        
        validations["passed"] = all_passed
        return validations
    
    async def run_all_scenarios(
        self,
        scenario_type: Optional[ScenarioType] = None,
        tags: Optional[List[str]] = None
    ) -> List[ScenarioResult]:
        """Run all scenarios or filtered subset."""
        # Get scenarios to run
        if scenario_type:
            scenarios = get_scenarios_by_type(scenario_type)
        elif tags:
            from tests.e2e.conversation_scenarios import get_scenarios_by_tags
            scenarios = get_scenarios_by_tags(tags)
        else:
            scenarios = get_all_scenarios()
        
        logger.info(f"Running {len(scenarios)} scenarios")
        
        # Run setup
        await self.setup()
        
        try:
            # Run each scenario
            for scenario in scenarios:
                result = await self.run_scenario(scenario)
                self.results.append(result)
                
                # Log result
                status = "PASSED" if result.passed else "FAILED"
                logger.info(
                    f"Scenario {scenario.name}: {status} "
                    f"({result.turns_completed}/{result.turns_total} turns)"
                )
                
                # Brief pause between scenarios
                await asyncio.sleep(2.0)
                
        finally:
            await self.teardown()
        
        return self.results
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate test report."""
        if not self.results:
            return {"error": "No test results"}
        
        # Calculate statistics
        total_scenarios = len(self.results)
        passed_scenarios = sum(1 for r in self.results if r.passed)
        total_turns = sum(r.turns_total for r in self.results)
        completed_turns = sum(r.turns_completed for r in self.results)
        
        # Group by scenario type
        by_type = {}
        for result in self.results:
            scenario_type = result.scenario_id.split("_")[0]
            if scenario_type not in by_type:
                by_type[scenario_type] = {"passed": 0, "failed": 0}
            
            if result.passed:
                by_type[scenario_type]["passed"] += 1
            else:
                by_type[scenario_type]["failed"] += 1
        
        # Failed scenarios details
        failed_scenarios = []
        for result in self.results:
            if not result.passed:
                failed_turns = [
                    {
                        "turn": tr.turn_number,
                        "message": tr.message,
                        "error": tr.error
                    }
                    for tr in result.turn_results if not tr.passed
                ]
                
                failed_scenarios.append({
                    "scenario_id": result.scenario_id,
                    "scenario_name": result.scenario_name,
                    "errors": result.errors,
                    "failed_turns": failed_turns,
                    "outcome_validation": result.outcome_validation
                })
        
        # Performance metrics
        avg_turn_time = sum(
            tr.response_time 
            for r in self.results 
            for tr in r.turn_results 
            if tr.speaker == "user"
        ) / max(1, sum(
            1 for r in self.results 
            for tr in r.turn_results 
            if tr.speaker == "user"
        ))
        
        return {
            "summary": {
                "total_scenarios": total_scenarios,
                "passed": passed_scenarios,
                "failed": total_scenarios - passed_scenarios,
                "pass_rate": passed_scenarios / total_scenarios if total_scenarios > 0 else 0,
                "total_turns": total_turns,
                "completed_turns": completed_turns,
                "turn_completion_rate": completed_turns / total_turns if total_turns > 0 else 0,
                "test_date": datetime.now().isoformat()
            },
            "by_type": by_type,
            "failed_scenarios": failed_scenarios,
            "performance": {
                "avg_response_time": avg_turn_time,
                "total_test_duration": sum(r.total_duration for r in self.results)
            }
        }
    
    def save_results(self, output_dir: str = "test_results"):
        """Save test results to files."""
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save detailed results
        results_path = os.path.join(output_dir, f"e2e_results_{timestamp}.json")
        with open(results_path, 'w') as f:
            results_data = [asdict(r) for r in self.results]
            # Convert datetime objects to strings
            for r in results_data:
                r['started_at'] = r['started_at'].isoformat()
                r['completed_at'] = r['completed_at'].isoformat()
            json.dump(results_data, f, indent=2)
        
        # Save report
        report = self.generate_report()
        report_path = os.path.join(output_dir, f"e2e_report_{timestamp}.json")
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Save markdown summary
        md_path = os.path.join(output_dir, f"e2e_summary_{timestamp}.md")
        self._save_markdown_summary(md_path, report)
        
        logger.info(f"Results saved to {output_dir}")
    
    def _save_markdown_summary(self, path: str, report: Dict[str, Any]):
        """Save markdown summary of results."""
        with open(path, 'w') as f:
            f.write("# E2E Test Results Summary\n\n")
            
            summary = report['summary']
            f.write("## Overall Results\n\n")
            f.write(f"- **Total Scenarios**: {summary['total_scenarios']}\n")
            f.write(f"- **Passed**: {summary['passed']} ({summary['pass_rate']:.1%})\n")
            f.write(f"- **Failed**: {summary['failed']}\n")
            f.write(f"- **Turn Completion Rate**: {summary['turn_completion_rate']:.1%}\n")
            f.write(f"- **Test Date**: {summary['test_date']}\n\n")
            
            f.write("## Results by Type\n\n")
            f.write("| Type | Passed | Failed | Pass Rate |\n")
            f.write("|------|--------|--------|----------|\n")
            
            for type_name, stats in report['by_type'].items():
                total = stats['passed'] + stats['failed']
                pass_rate = stats['passed'] / total if total > 0 else 0
                f.write(f"| {type_name} | {stats['passed']} | {stats['failed']} | {pass_rate:.1%} |\n")
            
            if report['failed_scenarios']:
                f.write("\n## Failed Scenarios\n\n")
                for failure in report['failed_scenarios']:
                    f.write(f"### {failure['scenario_name']} ({failure['scenario_id']})\n\n")
                    
                    if failure['errors']:
                        f.write("**Errors:**\n")
                        for error in failure['errors']:
                            f.write(f"- {error}\n")
                        f.write("\n")
                    
                    if failure['failed_turns']:
                        f.write("**Failed Turns:**\n")
                        for turn in failure['failed_turns']:
                            f.write(f"- Turn {turn['turn']}: \"{turn['message']}\" - {turn['error']}\n")
                        f.write("\n")
            
            f.write("\n## Performance\n\n")
            f.write(f"- **Average Response Time**: {report['performance']['avg_response_time']:.2f}s\n")
            f.write(f"- **Total Test Duration**: {report['performance']['total_test_duration']:.1f}s\n")


async def run_e2e_tests(
    scenario_type: Optional[ScenarioType] = None,
    tags: Optional[List[str]] = None,
    base_url: Optional[str] = None,
    ws_url: Optional[str] = None
) -> Dict[str, Any]:
    """Run E2E tests with specified filters."""
    runner = E2ETestRunner(base_url=base_url, ws_url=ws_url)
    
    # Run scenarios
    await runner.run_all_scenarios(scenario_type=scenario_type, tags=tags)
    
    # Generate report
    report = runner.generate_report()
    
    # Save results
    runner.save_results()
    
    return report


if __name__ == "__main__":
    # Example usage
    async def main():
        # Run all happy path scenarios
        report = await run_e2e_tests(scenario_type=ScenarioType.HAPPY_PATH)
        
        print("\n=== E2E Test Summary ===")
        print(f"Total Scenarios: {report['summary']['total_scenarios']}")
        print(f"Passed: {report['summary']['passed']}")
        print(f"Failed: {report['summary']['failed']}")
        print(f"Pass Rate: {report['summary']['pass_rate']:.1%}")
    
    asyncio.run(main())