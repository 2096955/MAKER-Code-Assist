#!/usr/bin/env python3
"""
Request Queue Manager: Prevents mutex contention on llama.cpp servers

Implements semaphore-based rate limiting to ensure only one request
per model server at a time, preventing the mutex.cc lock blocking errors.
"""

import asyncio
from typing import Dict, Any, Optional, Union
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RequestQueueManager:
    """
    Manages request queues for llama.cpp servers to prevent mutex contention.

    Each model server gets its own semaphore with max_concurrent=1 (sequential processing).
    This prevents the mutex.cc RAW lock blocking errors from llama.cpp.
    
    Note: Uses string values as dictionary keys to avoid enum type conflicts.
    Works with any AgentName enum that has .value attribute.
    """

    def __init__(self, max_concurrent_per_model: int = 1):
        """
        Initialize request queue manager.

        Args:
            max_concurrent_per_model: Max concurrent requests per model (default: 1 for sequential)
        """
        self.max_concurrent_per_model = max_concurrent_per_model

        # Semaphores for each model server (prevents concurrent access)
        # Use string values as keys to work with any AgentName enum
        agent_names = ["preprocessor", "planner", "coder", "reviewer", "voter"]
        self.semaphores: Dict[str, asyncio.Semaphore] = {
            agent_name: asyncio.Semaphore(max_concurrent_per_model)
            for agent_name in agent_names
        }

        # Request counters for observability
        self.request_counts: Dict[str, int] = {
            agent_name: 0 for agent_name in agent_names
        }
        self.active_requests: Dict[str, int] = {
            agent_name: 0 for agent_name in agent_names
        }

    async def enqueue_request(
        self,
        agent_name: Union[Enum, str],
        request_func,
        *args,
        **kwargs
    ) -> Any:
        """
        Enqueue a request to a model server, ensuring sequential processing.

        Args:
            agent_name: Which agent/model to use (AgentName enum or string)
            request_func: Async function to call (e.g., call_llm)
            *args, **kwargs: Arguments to pass to request_func

        Returns:
            Result from request_func
        """
        # Extract string value from enum if needed
        agent_key = agent_name.value if hasattr(agent_name, 'value') else str(agent_name)
        semaphore = self.semaphores[agent_key]

        # Wait for semaphore (blocks if another request is in flight)
        async with semaphore:
            self.active_requests[agent_key] += 1
            self.request_counts[agent_key] += 1

            try:
                logger.debug(
                    f"[RequestQueue] {agent_key}: "
                    f"Processing request #{self.request_counts[agent_key]} "
                    f"(active: {self.active_requests[agent_key]})"
                )

                # Execute the actual request
                result = await request_func(*args, **kwargs)

                return result

            finally:
                self.active_requests[agent_key] -= 1

    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics for observability"""
        return {
            "total_requests": {
                agent.value: count
                for agent, count in self.request_counts.items()
            },
            "active_requests": {
                agent.value: count
                for agent, count in self.active_requests.items()
            },
            "max_concurrent_per_model": self.max_concurrent_per_model
        }

    def reset_stats(self):
        """Reset request counters (useful for testing)"""
        for agent_name in self.request_counts:
            self.request_counts[agent_name] = 0
            self.active_requests[agent_name] = 0
