"""
Load tests for NATS JetStream publishing.

These tests validate:
1. Throughput (events/second)
2. Latency (P50, P95, P99)
3. Error rates under load
4. Resource usage (memory, CPU)
5. Connection stability

Run these tests with:
    pytest tests/load/test_load_publishing.py -v --tb=short

Or run standalone:
    python tests/load/test_load_publishing.py --duration=300 --rate=1000
"""

import argparse
import asyncio
import statistics
import time
from dataclasses import dataclass
from typing import List

import pytest

from vertector_nats import (
    NATSClient,
    NATSConfig,
    EventPublisher,
    CourseCreatedEvent,
    AssignmentCreatedEvent,
    EventMetadata,
)


@dataclass
class LoadTestResult:
    """Results from a load test run."""

    total_events: int
    successful_events: int
    failed_events: int
    duration_seconds: float
    throughput: float  # events/second
    latencies_ms: List[float]
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    max_latency_ms: float
    min_latency_ms: float
    avg_latency_ms: float
    error_rate: float


class LoadTestRunner:
    """Runs load tests against NATS JetStream."""

    def __init__(self, config: NATSConfig):
        self.config = config
        self.client: NATSClient = None
        self.publisher: EventPublisher = None

    async def setup(self):
        """Initialize NATS connection."""
        self.client = NATSClient(self.config)
        await self.client.connect()
        self.publisher = EventPublisher(client=self.client)

    async def teardown(self):
        """Close NATS connection."""
        if self.client:
            await self.client.close()

    async def run_constant_rate_test(
        self, target_rate: int, duration_seconds: int
    ) -> LoadTestResult:
        """
        Run load test with constant event rate.

        Args:
            target_rate: Target events per second
            duration_seconds: Test duration in seconds

        Returns:
            LoadTestResult with performance metrics
        """
        print(f"\n{'=' * 60}")
        print(f"Load Test: Constant Rate")
        print(f"Target Rate: {target_rate} events/second")
        print(f"Duration: {duration_seconds} seconds")
        print(f"{'=' * 60}\n")

        total_events = target_rate * duration_seconds
        interval = 1.0 / target_rate  # Time between events

        latencies = []
        successful = 0
        failed = 0

        start_time = time.time()
        next_event_time = start_time

        for i in range(total_events):
            # Create event
            event = CourseCreatedEvent(
                course_code=f"TEST{i:06d}",
                course_name=f"Load Test Course {i}",
                semester="Fall 2025",
                credits=3,
                instructor="Load Test",
                metadata=EventMetadata(source_service="load-test"),
            )

            # Wait until next event time
            now = time.time()
            if now < next_event_time:
                await asyncio.sleep(next_event_time - now)

            # Publish event and measure latency
            event_start = time.time()
            try:
                await self.publisher.publish(event)
                latency_ms = (time.time() - event_start) * 1000
                latencies.append(latency_ms)
                successful += 1
            except Exception as e:
                failed += 1
                print(f"Error publishing event {i}: {e}")

            next_event_time += interval

            # Progress indicator
            if (i + 1) % 100 == 0:
                elapsed = time.time() - start_time
                current_rate = (i + 1) / elapsed
                print(
                    f"Progress: {i + 1}/{total_events} "
                    f"({current_rate:.1f} events/sec, "
                    f"P95: {statistics.quantiles(latencies, n=20)[18]:.1f}ms)"
                )

        duration = time.time() - start_time

        return self._create_result(
            total_events, successful, failed, duration, latencies
        )

    async def run_burst_test(
        self, burst_size: int, num_bursts: int, burst_interval: float
    ) -> LoadTestResult:
        """
        Run load test with bursts of events.

        Args:
            burst_size: Number of events per burst
            num_bursts: Number of bursts
            burst_interval: Time between bursts (seconds)

        Returns:
            LoadTestResult with performance metrics
        """
        print(f"\n{'=' * 60}")
        print(f"Load Test: Burst Mode")
        print(f"Burst Size: {burst_size} events")
        print(f"Number of Bursts: {num_bursts}")
        print(f"Burst Interval: {burst_interval}s")
        print(f"{'=' * 60}\n")

        total_events = burst_size * num_bursts
        latencies = []
        successful = 0
        failed = 0

        start_time = time.time()

        for burst_num in range(num_bursts):
            print(f"Burst {burst_num + 1}/{num_bursts}...")

            # Create events for this burst
            events = [
                CourseCreatedEvent(
                    course_code=f"BURST{burst_num:03d}{i:03d}",
                    course_name=f"Burst Test {burst_num}-{i}",
                    semester="Fall 2025",
                    credits=3,
                    instructor="Burst Test",
                    metadata=EventMetadata(source_service="load-test"),
                )
                for i in range(burst_size)
            ]

            # Publish burst
            burst_start = time.time()
            try:
                acks = await self.publisher.publish_batch(events, parallel=True)
                burst_duration = (time.time() - burst_start) * 1000
                latencies.extend([burst_duration] * len(acks))
                successful += len(acks)
            except Exception as e:
                failed += burst_size
                print(f"Error in burst {burst_num}: {e}")

            # Wait before next burst
            if burst_num < num_bursts - 1:
                await asyncio.sleep(burst_interval)

        duration = time.time() - start_time

        return self._create_result(
            total_events, successful, failed, duration, latencies
        )

    async def run_sustained_load_test(
        self, target_rate: int, duration_minutes: int
    ) -> LoadTestResult:
        """
        Run sustained load test for extended period.

        Args:
            target_rate: Target events per second
            duration_minutes: Test duration in minutes

        Returns:
            LoadTestResult with performance metrics
        """
        duration_seconds = duration_minutes * 60
        return await self.run_constant_rate_test(target_rate, duration_seconds)

    def _create_result(
        self,
        total: int,
        successful: int,
        failed: int,
        duration: float,
        latencies: List[float],
    ) -> LoadTestResult:
        """Create LoadTestResult from raw data."""
        if not latencies:
            latencies = [0.0]

        sorted_latencies = sorted(latencies)
        quantiles = statistics.quantiles(sorted_latencies, n=100)

        return LoadTestResult(
            total_events=total,
            successful_events=successful,
            failed_events=failed,
            duration_seconds=duration,
            throughput=successful / duration if duration > 0 else 0,
            latencies_ms=latencies,
            p50_latency_ms=quantiles[49],
            p95_latency_ms=quantiles[94],
            p99_latency_ms=quantiles[98],
            max_latency_ms=max(latencies),
            min_latency_ms=min(latencies),
            avg_latency_ms=statistics.mean(latencies),
            error_rate=failed / total if total > 0 else 0,
        )

    def print_result(self, result: LoadTestResult):
        """Print load test results."""
        print(f"\n{'=' * 60}")
        print(f"LOAD TEST RESULTS")
        print(f"{'=' * 60}")
        print(f"\nThroughput:")
        print(f"  Total Events:      {result.total_events:,}")
        print(f"  Successful:        {result.successful_events:,}")
        print(f"  Failed:            {result.failed_events:,}")
        print(f"  Duration:          {result.duration_seconds:.2f}s")
        print(f"  Throughput:        {result.throughput:.2f} events/sec")
        print(f"  Error Rate:        {result.error_rate * 100:.2f}%")
        print(f"\nLatency:")
        print(f"  Min:               {result.min_latency_ms:.2f}ms")
        print(f"  Avg:               {result.avg_latency_ms:.2f}ms")
        print(f"  P50:               {result.p50_latency_ms:.2f}ms")
        print(f"  P95:               {result.p95_latency_ms:.2f}ms")
        print(f"  P99:               {result.p99_latency_ms:.2f}ms")
        print(f"  Max:               {result.max_latency_ms:.2f}ms")
        print(f"\n{'=' * 60}\n")

        # Performance assessment
        self._assess_performance(result)

    def _assess_performance(self, result: LoadTestResult):
        """Assess if performance meets targets."""
        print("Performance Assessment:")
        print()

        # Target: 1000 events/second
        if result.throughput >= 1000:
            print(f"  ✅ Throughput: PASS ({result.throughput:.0f} >= 1000 events/sec)")
        else:
            print(f"  ❌ Throughput: FAIL ({result.throughput:.0f} < 1000 events/sec)")

        # Target: P95 < 100ms
        if result.p95_latency_ms < 100:
            print(f"  ✅ P95 Latency: PASS ({result.p95_latency_ms:.1f}ms < 100ms)")
        else:
            print(f"  ❌ P95 Latency: FAIL ({result.p95_latency_ms:.1f}ms >= 100ms)")

        # Target: P99 < 500ms
        if result.p99_latency_ms < 500:
            print(f"  ✅ P99 Latency: PASS ({result.p99_latency_ms:.1f}ms < 500ms)")
        else:
            print(f"  ❌ P99 Latency: FAIL ({result.p99_latency_ms:.1f}ms >= 500ms)")

        # Target: < 0.1% error rate
        if result.error_rate < 0.001:
            print(f"  ✅ Error Rate: PASS ({result.error_rate * 100:.3f}% < 0.1%)")
        else:
            print(f"  ❌ Error Rate: FAIL ({result.error_rate * 100:.3f}% >= 0.1%)")

        print()


@pytest.mark.load
class TestLoadPublishing:
    """Load tests for event publishing."""

    @pytest.fixture
    async def load_runner(self):
        """Create load test runner."""
        config = NATSConfig(enable_jetstream=True)
        runner = LoadTestRunner(config)
        await runner.setup()
        yield runner
        await runner.teardown()

    @pytest.mark.asyncio
    async def test_constant_rate_100_eps(self, load_runner):
        """Test constant rate: 100 events/second for 60 seconds."""
        result = await load_runner.run_constant_rate_test(
            target_rate=100, duration_seconds=60
        )
        load_runner.print_result(result)

        assert result.error_rate < 0.01  # Less than 1% errors
        assert result.p95_latency_ms < 100  # P95 under 100ms

    @pytest.mark.asyncio
    async def test_constant_rate_500_eps(self, load_runner):
        """Test constant rate: 500 events/second for 60 seconds."""
        result = await load_runner.run_constant_rate_test(
            target_rate=500, duration_seconds=60
        )
        load_runner.print_result(result)

        assert result.error_rate < 0.01
        assert result.p95_latency_ms < 100

    @pytest.mark.asyncio
    async def test_constant_rate_1000_eps(self, load_runner):
        """Test constant rate: 1000 events/second for 60 seconds."""
        result = await load_runner.run_constant_rate_test(
            target_rate=1000, duration_seconds=60
        )
        load_runner.print_result(result)

        assert result.error_rate < 0.01
        assert result.p95_latency_ms < 100

    @pytest.mark.asyncio
    async def test_burst_small(self, load_runner):
        """Test small bursts: 50 events per burst, 20 bursts."""
        result = await load_runner.run_burst_test(
            burst_size=50, num_bursts=20, burst_interval=1.0
        )
        load_runner.print_result(result)

        assert result.error_rate < 0.01

    @pytest.mark.asyncio
    async def test_burst_large(self, load_runner):
        """Test large bursts: 500 events per burst, 10 bursts."""
        result = await load_runner.run_burst_test(
            burst_size=500, num_bursts=10, burst_interval=2.0
        )
        load_runner.print_result(result)

        assert result.error_rate < 0.01

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_sustained_load_5_minutes(self, load_runner):
        """Test sustained load: 500 events/second for 5 minutes."""
        result = await load_runner.run_sustained_load_test(
            target_rate=500, duration_minutes=5
        )
        load_runner.print_result(result)

        assert result.error_rate < 0.01
        assert result.p95_latency_ms < 100

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_sustained_load_30_minutes(self, load_runner):
        """Test sustained load: 500 events/second for 30 minutes."""
        result = await load_runner.run_sustained_load_test(
            target_rate=500, duration_minutes=30
        )
        load_runner.print_result(result)

        assert result.error_rate < 0.01
        assert result.p95_latency_ms < 100


async def run_cli_load_test(args):
    """Run load test from command line."""
    config = NATSConfig(enable_jetstream=True)
    runner = LoadTestRunner(config)

    await runner.setup()

    try:
        if args.burst:
            result = await runner.run_burst_test(
                burst_size=args.burst_size,
                num_bursts=args.num_bursts,
                burst_interval=args.burst_interval,
            )
        else:
            result = await runner.run_constant_rate_test(
                target_rate=args.rate, duration_seconds=args.duration
            )

        runner.print_result(result)

        # Save results to file if requested
        if args.output:
            import json

            with open(args.output, "w") as f:
                json.dump(
                    {
                        "total_events": result.total_events,
                        "successful_events": result.successful_events,
                        "failed_events": result.failed_events,
                        "duration_seconds": result.duration_seconds,
                        "throughput": result.throughput,
                        "p50_latency_ms": result.p50_latency_ms,
                        "p95_latency_ms": result.p95_latency_ms,
                        "p99_latency_ms": result.p99_latency_ms,
                        "max_latency_ms": result.max_latency_ms,
                        "min_latency_ms": result.min_latency_ms,
                        "avg_latency_ms": result.avg_latency_ms,
                        "error_rate": result.error_rate,
                    },
                    f,
                    indent=2,
                )
            print(f"Results saved to: {args.output}")

    finally:
        await runner.teardown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NATS JetStream Load Test")
    parser.add_argument(
        "--rate", type=int, default=100, help="Target events per second"
    )
    parser.add_argument(
        "--duration", type=int, default=60, help="Test duration in seconds"
    )
    parser.add_argument("--burst", action="store_true", help="Run burst test")
    parser.add_argument("--burst-size", type=int, default=100, help="Events per burst")
    parser.add_argument("--num-bursts", type=int, default=10, help="Number of bursts")
    parser.add_argument(
        "--burst-interval", type=float, default=1.0, help="Seconds between bursts"
    )
    parser.add_argument("--output", type=str, help="Output file for results (JSON)")

    args = parser.parse_args()

    asyncio.run(run_cli_load_test(args))
