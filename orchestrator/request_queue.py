#!/usr/bin/env python3
"""
Request Queue Manager: Prevents mutex contention on llama.cpp servers

Implements semaphore-based rate limiting to ensure only one request
per model server at a time, preventing the mutex.cc lock blocking errors.
"""

import asyncio
from typing import Dict, Any, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AgentName(Enum):
    PREPROCESSOR = "preprocessor"
    PLANNER = "planner"
    CODER = "coder"
    REVIEWER = "reviewer"
    VOTER = "voter"


class RequestQueueManager:
    """
    Manages request queues for llama.cpp servers to prevent mutex contention.

    Each model server gets its own semaphore with max_concurrent=1 (sequential processing).
    This prevents the mutex.cc RAW lock blocking errors from llama.cpp.
    """

    def __init__(self, max_concurrent_per_model: int = 1):
        """
        Initialize request queue manager.

        Args:
            max_concurrent_per_model: Max concurrent requests per model (default: 1 for sequential)
        """
        self.max_concurrent_per_model = max_concurrent_per_model

        # Semaphores for each model server (prevents concurrent access)
        self.semaphores: Dict[AgentName, asyncio.Semaphore] = {
            agent: asyncio.Semaphore(max_concurrent_per_model)
            for agent in AgentName
        }

        # Request counters for observability
        self.request_counts: Dict[AgentName, int] = {
            agent: 0 for agent in AgentName
        }
        self.active_requests: Dict[AgentName, int] = {
            agent: 0 for agent in AgentName
        }

    async def enqueue_request(
        self,
        agent_name: AgentName,
        request_func,
        *args,
        **kwargs
    ) -> Any:
        """
        Enqueue a request to a model server, ensuring sequential processing.

        Args:
            agent_name: Which agent/model to use
            request_func: Async function to call (e.g., call_llm)
            *args, **kwargs: Arguments to pass to request_func

        Returns:
            Result from request_func
        """
        semaphore = self.semaphores[agent_name]

        # Wait for semaphore (blocks if another request is in flight)
        async with semaphore:
            self.active_requests[agent_name] += 1
            self.request_counts[agent_name] += 1

            try:
                logger.debug(
                    f"[RequestQueue] {agent_name.value}: "
                    f"Processing request #{self.request_counts[agent_name]} "
                    f"(active: {self.active_requests[agent_name]})"
                )

                # Execute the actual request
                result = await request_func(*args, **kwargs)

                return result

            finally:
                self.active_requests[agent_name] -= 1

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
        for agent in AgentName:
            self.request_counts[agent] = 0
            self.active_requests[agent] = 0
