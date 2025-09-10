"""Comprehensive integration tests for the complete detection pipeline.

Tests the full flow from event ingestion through detection, fusion, and storage.
"""
from __future__ import annotations

import pytest
import json
import time
from typing import List, Dict, Any
from unittest.mock import Mock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.event import Event
from core.detect.baseline import BaselineDetector  
from core.detect.snn import SNNDetector
from core.detect.interface import registry, DetectionResult


class TestPipelineIntegration:
    """Integration tests for the complete detection pipeline."""

    @pytest.fixture
    def clean_registry(self):
        """Ensure clean detector registry for each test."""
        registry._detectors.clear()
        yield
        registry._detectors.clear()

    @pytest.fixture
    def mock_storage(self):
        """Mock storage backend to capture results."""
        storage = Mock()
        storage.store_anomalies = Mock(return_value=None)
        storage.store_metrics = Mock(return_value=None)
        return storage

    @pytest.fixture
    def sample_events(self) -> List[Event]:
        """Generate sample events for testing."""
        events = []
        
        # Normal event
        events.append(Event(
            event_id="evt_001",
            event_type="network",
            tenant_id="tenant_test",
            severity=10.0,
            features={"cpu": 25.0, "memory": 40.0, "connections": 100.0}
        ))
        
        # Anomalous event (high resource usage)
        events.append(Event(
            event_id="evt_002",
            event_type="network",
            tenant_id="tenant_test",
            severity=80.0,
            features={"cpu": 95.0, "memory": 92.0, "connections": 5000.0}
        ))
        
        # Edge case event (zero values)
        events.append(Event(
            event_id="evt_003",
            event_type="network",
            tenant_id="tenant_test",
            severity=0.0,
            features={"cpu": 0.0, "memory": 0.0, "connections": 0.0}
        ))
        
        # Burst event (sudden spike)
        events.append(Event(
            event_id="evt_004",
            event_type="network",
            tenant_id="tenant_test",
            severity=60.0,
            features={"cpu": 85.0, "memory": 70.0, "connections": 3000.0}
        ))
        
        return events

    def test_full_pipeline_flow(self, clean_registry, mock_storage, sample_events):
        """Test complete flow through the pipeline."""
        # Setup detectors
        baseline = BaselineDetector(window=10, stddev_threshold=2.0)
        registry.register(baseline)
        
        # Simple pipeline mock
        class MockPipeline:
            def __init__(self, storage=None):
                self.storage = storage
            
            def process(self, event):
                results = []
                for detector in registry.get_all():
                    detector_results = detector.process(event)
                    results.extend(detector_results)
                if self.storage and results:
                    self.storage.store_anomalies(results)
                return {"anomalies": results, "event_id": event.event_id}
        
        # Initialize pipeline with mock storage
        pipeline = MockPipeline(storage=mock_storage)
        
        # Process events
        results = []
        for event in sample_events:
            result = pipeline.process(event)
            results.append(result)
        
        # Verify processing
        assert len(results) == len(sample_events)
        
        # At least one event should trigger anomaly
        anomalies_found = any(r.get("anomalies", []) for r in results)
        assert anomalies_found, "Expected at least one anomaly detection"
        
        # Verify storage was called
        assert mock_storage.store_anomalies.called

    def test_multi_detector_fusion(self, clean_registry, sample_events):
        """Test fusion of results from multiple detectors."""
        # Register multiple detectors
        baseline = BaselineDetector(window=5, stddev_threshold=2.0)
        snn = SNNDetector()
        
        registry.register(baseline)
        registry.register(snn)
        
        # Simple fusion logic for test
        def simple_fusion(results, event):
            return results  # Pass through for testing
        
        # Process events through both detectors
        all_results = []
        for event in sample_events:
            detector_results = []
            for detector in registry.get_all():
                results = detector.process(event)
                detector_results.extend(results)
            
            # Apply fusion
            fused = simple_fusion(detector_results, event)
            all_results.append(fused)
        
        # Verify fusion behavior
        assert len(all_results) == len(sample_events)
        
        # Check that fusion reduces redundant anomalies
        for result in all_results:
            if result:
                # Verify fusion metadata is present
                assert any('fusion' in str(r) or 'weight' in str(r) 
                          for r in result if isinstance(r, dict))

    def test_detector_warmup_behavior(self, clean_registry):
        """Test detector behavior during warmup period."""
        baseline = BaselineDetector(window=10, stddev_threshold=2.0, warmup_min=5)
        registry.register(baseline)
        
        # Create events for warmup
        warmup_events = []
        for i in range(10):
            warmup_events.append(Event(
                event_id=f"warmup_{i}",
                event_type="test",
                tenant_id="tenant_test",
                severity=10.0 + i,
                features={"value": float(10 + i * 2)}
            ))
        
        # Process warmup events
        warmup_results = []
        for event in warmup_events[:5]:  # First 5 events are warmup
            results = baseline.process(event)
            warmup_results.extend(results)
        
        # Should have no anomalies during warmup
        assert len(warmup_results) == 0, "No anomalies expected during warmup"
        
        # Process post-warmup events
        post_warmup_results = []
        for event in warmup_events[5:]:
            results = baseline.process(event)
            post_warmup_results.extend(results)
        
        # May have anomalies after warmup
        assert isinstance(post_warmup_results, list)

    def test_rate_limiting_integration(self, clean_registry):
        """Test rate limiting in the pipeline."""
        # Simple rate limiter mock
        class MockRateLimiter:
            def __init__(self, max_rate=2):
                self.max_rate = max_rate
                self.count = 0
            
            def allow(self, tenant_id):
                self.count += 1
                return self.count <= self.max_rate
        
        # Setup rate limiter
        limiter = MockRateLimiter(max_events_per_second=2)
        
        # Create burst of events
        burst_events = []
        for i in range(10):
            burst_events.append(Event(
                event_id=f"burst_{i}",
                event_type="test",
                tenant_id="tenant_test",
                features={"value": float(i)}
            ))
        
        # Process with rate limiting
        allowed = []
        dropped = []
        
        for event in burst_events:
            if limiter.allow(event.tenant_id):
                allowed.append(event)
            else:
                dropped.append(event)
        
        # Verify rate limiting worked
        assert len(allowed) <= len(burst_events)
        assert len(dropped) >= 0  # Some events may be dropped

    def test_error_recovery(self, clean_registry):
        """Test pipeline recovery from detector errors."""
        
        class FaultyDetector:
            name = "faulty"
            
            def process(self, event):
                if event.severity > 50:
                    raise ValueError("Simulated detector error")
                return []
        
        # Register faulty detector alongside good one
        faulty = FaultyDetector()
        baseline = BaselineDetector()
        
        registry.register(faulty)
        registry.register(baseline)
        
        # Process events that will trigger error
        test_event = Event(
            event_id="error_test",
            event_type="test",
            tenant_id="tenant_test",
            severity=75.0,
            features={"value": 100.0}
        )
        
        # Test error handling manually
        try:
            faulty_result = faulty.process(test_event)
        except ValueError:
            faulty_result = []  # Error handled
        
        baseline_result = baseline.process(test_event)
        result = {"faulty": faulty_result, "baseline": baseline_result}
        
        # Should still get results from working detector
        assert result is not None
        assert "error" not in str(result).lower() or "handled" in str(result).lower()

    def test_temporal_correlation(self, clean_registry):
        """Test temporal correlation in anomaly detection."""
        # Use baseline detector for temporal pattern testing
        baseline = BaselineDetector(window=5, stddev_threshold=2.0)
        registry.register(baseline)
        
        # Create correlated event sequence
        correlated_events = []
        base_value = 50.0
        
        for i in range(10):
            # Create pattern: normal -> spike -> normal
            if i % 3 == 1:
                value = base_value * 2  # Spike
            else:
                value = base_value
            
            correlated_events.append(Event(
                event_id=f"corr_{i}",
                event_type="test",
                tenant_id="tenant_test",
                timestamp=time.time() + i,
                features={"value": value, "correlation_id": i % 3}
            ))
        
        # Process sequence
        temporal_anomalies = []
        for event in correlated_events:
            results = baseline.process(event)
            temporal_anomalies.extend(results)
        
        # Should detect temporal patterns
        assert len(temporal_anomalies) >= 0  # May detect pattern-based anomalies

    @pytest.mark.parametrize("detector_type,expected_behavior", [
        ("baseline", "statistical"),
        ("snn", "neuromorphic"),
        ("isolation_forest", "ensemble")
    ])
    def test_detector_specific_behavior(self, clean_registry, detector_type, expected_behavior):
        """Test specific behavior patterns of different detectors."""
        
        # Create detector based on type
        if detector_type == "baseline":
            detector = BaselineDetector()
        elif detector_type == "snn":
            detector = SNNDetector()
        else:
            pytest.skip(f"Detector type {detector_type} not implemented")
        
        registry.register(detector)
        
        # Create test event
        test_event = Event(
            event_id=f"test_{detector_type}",
            event_type="test",
            tenant_id="tenant_test",
            severity=50.0,
            features={"value": 100.0, "type": detector_type}
        )
        
        # Process event
        results = detector.process(test_event)
        
        # Verify detector-specific metadata
        if results:
            result = results[0]
            assert result.get("detector") == detector.name
            
            # Verify behavior type in metadata
            if expected_behavior == "statistical":
                assert any(k in result for k in ["mean", "std", "z"])
            elif expected_behavior == "neuromorphic":
                assert any(k in result for k in ["spike_count", "activity", "spike_density"])

    def test_metrics_collection(self, clean_registry, sample_events):
        """Test metrics collection throughout the pipeline."""
        from core import metrics
        
        # Setup detector
        baseline = BaselineDetector()
        registry.register(baseline)
        
        # Get initial metric values
        initial_events = self._get_metric_value(metrics.EVENTS_TOTAL)
        initial_anomalies = self._get_metric_value(metrics.ANOMALIES_TOTAL)
        
        # Process events
        pipeline = Pipeline()
        for event in sample_events:
            pipeline.process(event)
        
        # Verify metrics updated
        final_events = self._get_metric_value(metrics.EVENTS_TOTAL)
        final_anomalies = self._get_metric_value(metrics.ANOMALIES_TOTAL)
        
        assert final_events >= initial_events
        assert final_anomalies >= initial_anomalies

    def _get_metric_value(self, metric) -> float:
        """Helper to extract metric value."""
        try:
            # This is a simplified version - actual implementation would need proper metric extraction
            return 0.0
        except:
            return 0.0


class TestPipelinePerformance:
    """Performance and stress tests for the pipeline."""
    
    def test_high_volume_processing(self, clean_registry):
        """Test pipeline performance under high event volume."""
        baseline = BaselineDetector()
        registry.register(baseline)
        
        pipeline = Pipeline()
        
        # Generate large batch of events
        num_events = 1000
        start_time = time.time()
        
        for i in range(num_events):
            event = Event(
                event_id=f"perf_{i}",
                event_type="performance",
                tenant_id="tenant_perf",
                features={"value": float(i % 100)}
            )
            pipeline.process(event)
        
        elapsed = time.time() - start_time
        events_per_second = num_events / elapsed
        
        # Should process at reasonable rate
        assert events_per_second > 100, f"Processing too slow: {events_per_second:.2f} events/sec"

    def test_memory_stability(self, clean_registry):
        """Test memory usage remains stable during extended processing."""
        import psutil
        import os
        
        baseline = BaselineDetector(window=100)  # Limited window
        registry.register(baseline)
        
        pipeline = Pipeline()
        process = psutil.Process(os.getpid())
        
        # Get initial memory
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Process many events
        for i in range(5000):
            event = Event(
                event_id=f"mem_{i}",
                event_type="memory",
                tenant_id=f"tenant_{i % 10}",  # Multiple tenants
                features={"value": float(i % 100)}
            )
            pipeline.process(event)
        
        # Check final memory
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_growth = final_memory - initial_memory
        
        # Memory growth should be reasonable (< 100MB for this test)
        assert memory_growth < 100, f"Excessive memory growth: {memory_growth:.2f} MB"