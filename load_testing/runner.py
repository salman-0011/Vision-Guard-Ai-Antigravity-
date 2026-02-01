"""
VisionGuard AI - Load Test Runner

Orchestrates load test execution and collects results.
"""

import time
import logging
import sys
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime

from .camera_simulator import MultiCameraSimulator, SimulatorConfig
from .metrics_collector import MetricsCollector
from .scenarios import ScenarioConfig, ScenarioType, ALL_SCENARIOS, get_scenario

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Result of a load test run."""
    scenario_name: str
    started_at: str
    ended_at: str
    duration_seconds: float
    
    # Pass/Fail
    passed: bool
    failure_reasons: List[str]
    
    # Metrics
    peak_queue_size: int
    avg_queue_size: float
    final_stream_length: int
    redis_uptime_pct: float
    
    # Throughput
    avg_fps: float
    peak_fps: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LoadTestRunner:
    """
    Runs load test scenarios and collects results.
    
    Usage:
        runner = LoadTestRunner()
        result = runner.run_scenario("normal")
        print(result)
    """
    
    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379
    ):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.collector: Optional[MetricsCollector] = None
        self.simulator: Optional[MultiCameraSimulator] = None
    
    def run_scenario(
        self,
        scenario: ScenarioConfig,
        verbose: bool = True
    ) -> TestResult:
        """
        Run a single test scenario.
        
        Args:
            scenario: Scenario configuration
            verbose: Print progress to console
            
        Returns:
            TestResult with pass/fail and metrics
        """
        start_time = datetime.now()
        logger.info(f"="*60)
        logger.info(f"Starting scenario: {scenario.name}")
        logger.info(f"Description: {scenario.description}")
        logger.info(f"Duration: {scenario.duration_seconds}s")
        logger.info(f"="*60)
        
        # Initialize metrics collector
        self.collector = MetricsCollector(
            redis_host=self.redis_host,
            redis_port=self.redis_port,
            sample_interval_sec=1.0
        )
        
        if not self.collector.start():
            return TestResult(
                scenario_name=scenario.name,
                started_at=start_time.isoformat(),
                ended_at=datetime.now().isoformat(),
                duration_seconds=0,
                passed=False,
                failure_reasons=["Failed to connect to Redis"],
                peak_queue_size=0,
                avg_queue_size=0,
                final_stream_length=0,
                redis_uptime_pct=0,
                avg_fps=0,
                peak_fps=0
            )
        
        # Initialize camera simulator
        self.simulator = MultiCameraSimulator(
            num_cameras=scenario.num_cameras,
            base_fps=scenario.base_fps,
            motion_probability=scenario.motion_probability,
            redis_host=self.redis_host,
            redis_port=self.redis_port
        )
        
        started = self.simulator.start_all()
        logger.info(f"Started {started}/{scenario.num_cameras} camera simulators")
        
        try:
            # Run test
            test_start = time.time()
            elapsed = 0
            last_log = 0
            
            while elapsed < scenario.duration_seconds:
                time.sleep(1.0)
                elapsed = time.time() - test_start
                
                # Handle burst mode trigger
                if scenario.scenario_type == ScenarioType.BURST:
                    if scenario.burst_start_sec <= elapsed < scenario.burst_start_sec + scenario.burst_duration_sec:
                        self.simulator.enable_burst_mode(scenario.burst_duration_sec)
                        if elapsed - last_log >= 5 or elapsed == scenario.burst_start_sec:
                            logger.warning(">>> BURST MODE ACTIVE <<<")
                    else:
                        self.simulator.disable_burst_mode()
                
                # Log progress every 10 seconds
                if elapsed - last_log >= 10:
                    latest = self.collector.get_latest()
                    if latest and verbose:
                        total_queue = (
                            latest.redis_queue_critical +
                            latest.redis_queue_high +
                            latest.redis_queue_medium
                        )
                        logger.info(
                            f"[{int(elapsed)}s] Queue: {total_queue}, "
                            f"Stream: {latest.redis_stream_length}, "
                            f"FPS: {latest.frames_per_second}"
                        )
                    last_log = elapsed
                    
        except KeyboardInterrupt:
            logger.warning("Test interrupted by user")
        finally:
            # Stop everything
            logger.info("Stopping simulators...")
            self.simulator.stop_all()
            
            # Allow metrics to settle
            time.sleep(2)
            
            # Collect final results
            end_time = datetime.now()
            summary = self.collector.get_summary(last_n_seconds=int(scenario.duration_seconds))
            
            self.collector.stop()
        
        # Analyze results
        failure_reasons = []
        
        # Check queue size
        peak_queue = (
            summary.get("queue_critical", {}).get("max", 0) +
            summary.get("queue_high", {}).get("max", 0) +
            summary.get("queue_medium", {}).get("max", 0)
        )
        
        if peak_queue > scenario.max_queue_size:
            failure_reasons.append(
                f"Peak queue size {peak_queue} exceeded threshold {scenario.max_queue_size}"
            )
        
        # Check Redis uptime
        redis_uptime = summary.get("redis_connected_pct", 0)
        if redis_uptime < scenario.min_redis_uptime_pct:
            failure_reasons.append(
                f"Redis uptime {redis_uptime}% below threshold {scenario.min_redis_uptime_pct}%"
            )
        
        result = TestResult(
            scenario_name=scenario.name,
            started_at=start_time.isoformat(),
            ended_at=end_time.isoformat(),
            duration_seconds=(end_time - start_time).total_seconds(),
            passed=len(failure_reasons) == 0,
            failure_reasons=failure_reasons,
            peak_queue_size=peak_queue,
            avg_queue_size=round(
                summary.get("queue_medium", {}).get("avg", 0) +
                summary.get("queue_high", {}).get("avg", 0) +
                summary.get("queue_critical", {}).get("avg", 0), 1
            ),
            final_stream_length=summary.get("stream_length", {}).get("final", 0),
            redis_uptime_pct=redis_uptime,
            avg_fps=summary.get("throughput_fps", {}).get("avg", 0),
            peak_fps=summary.get("throughput_fps", {}).get("max", 0)
        )
        
        # Print result
        logger.info(f"="*60)
        logger.info(f"SCENARIO COMPLETE: {scenario.name}")
        logger.info(f"Result: {'PASS' if result.passed else 'FAIL'}")
        if not result.passed:
            for reason in result.failure_reasons:
                logger.error(f"  - {reason}")
        logger.info(f"Peak Queue: {result.peak_queue_size}")
        logger.info(f"Redis Uptime: {result.redis_uptime_pct}%")
        logger.info(f"Avg FPS: {result.avg_fps}")
        logger.info(f"="*60)
        
        return result
    
    def run_all(self, verbose: bool = True) -> List[TestResult]:
        """Run all scenarios and return results."""
        results = []
        for scenario in ALL_SCENARIOS:
            result = self.run_scenario(scenario, verbose)
            results.append(result)
            
            # Short break between scenarios
            if scenario != ALL_SCENARIOS[-1]:
                logger.info("Waiting 10 seconds before next scenario...")
                time.sleep(10)
        
        return results


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="VisionGuard AI Load Test Runner")
    parser.add_argument(
        "--scenario",
        type=str,
        default="normal",
        help="Scenario to run: normal, burst, slow, redis, or 'all'"
    )
    parser.add_argument("--redis-host", type=str, default="localhost")
    parser.add_argument("--redis-port", type=int, default=6379)
    parser.add_argument("--quiet", action="store_true", help="Reduce output")
    
    args = parser.parse_args()
    
    runner = LoadTestRunner(
        redis_host=args.redis_host,
        redis_port=args.redis_port
    )
    
    if args.scenario.lower() == "all":
        results = runner.run_all(verbose=not args.quiet)
        
        # Summary
        passed = sum(1 for r in results if r.passed)
        logger.info(f"\n{'='*60}")
        logger.info(f"ALL TESTS COMPLETE: {passed}/{len(results)} passed")
        
        for r in results:
            status = "✓ PASS" if r.passed else "✗ FAIL"
            logger.info(f"  {status}: {r.scenario_name}")
        
        sys.exit(0 if passed == len(results) else 1)
    else:
        scenario = get_scenario(args.scenario)
        if not scenario:
            logger.error(f"Unknown scenario: {args.scenario}")
            logger.error(f"Available: normal, burst, slow, redis, all")
            sys.exit(1)
        
        result = runner.run_scenario(scenario, verbose=not args.quiet)
        sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
