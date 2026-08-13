import asyncio
from typing import List, Callable, Coroutine, Any, Optional
from .logger import log_info, log_success, log_error, log_step

class Step:
    """Represents a single atomic action step in the automation pipeline."""
    def __init__(self, name: str, description: str, action: Callable[..., Coroutine[Any, Any, Any]], verify: Optional[Callable[..., Coroutine[Any, Any, bool]]] = None):
        self.name = name
        self.description = description
        self.action = action
        self.verify = verify

def step_action(name: str, description: str, verify: Optional[Callable] = None):
    """Decorator to define a pipeline step easily."""
    def decorator(func: Callable):
        return Step(name=name, description=description, action=func, verify=verify)
    return decorator

class PipelineEngine:
    """Pipeline Engine managing sequential coroutine actions, verifications, and post-success cleanups."""

    def __init__(self, name: str = "Automation Pipeline"):
        self.name = name
        self.steps: List[Step] = []
        self.cleanup_steps: List[Step] = []

    def add_step(self, step: Step):
        """Add a sequential test step."""
        self.steps.append(step)

    def add_cleanup_step(self, step: Step):
        """Add a cleanup step that runs ONLY when all test steps succeed."""
        self.cleanup_steps.append(step)

    async def run(self, context: dict = None) -> bool:
        """Run all steps sequentially with fail-fast enforcement."""
        if context is None:
            context = {}

        print(f"\n========================================================================")
        print(f"STARTING PIPELINE: {self.name}")
        print(f"Total Steps: {len(self.steps)} | Cleanup Steps: {len(self.cleanup_steps)}")
        print(f"========================================================================\n")

        all_passed = True

        for index, step in enumerate(self.steps, 1):
            log_step(index, f"{step.name} - {step.description}")
            try:
                # Run action coroutine
                result = await step.action(context)
                context[f"result_step_{index}"] = result

                # Run verification coroutine if provided
                if step.verify:
                    log_info(f"Running verification for step: {step.name}...")
                    verify_passed = await step.verify(context)
                    if not verify_passed:
                        raise RuntimeError(f"Verification failed for step '{step.name}'")

                log_success(f"Step {index} ({step.name}) COMPLETED SUCCESSFULLY")

            except Exception as e:
                log_error(f"Step {index} ({step.name}) FAILED: {e}")
                all_passed = False
                break  # Fail-fast: stop pipeline on first error

        if all_passed:
            print(f"\n------------------------------------------------------------------------")
            print(f"ALL TEST STEPS PASSED SUCCESSFULLY! Executing post-success cleanups...")
            print(f"------------------------------------------------------------------------\n")
            for index, cleanup_step in enumerate(self.cleanup_steps, 1):
                log_step(index, f"CLEANUP: {cleanup_step.name}")
                try:
                    await cleanup_step.action(context)
                    log_success(f"Cleanup Step '{cleanup_step.name}' COMPLETED")
                except Exception as e:
                    log_error(f"Cleanup Step '{cleanup_step.name}' encountered error: {e}")

            print(f"\n========================================================================")
            print(f"PIPELINE {self.name} EXECUTED SUCCESSFULLY")
            print(f"========================================================================\n")
            return True
        else:
            print(f"\n========================================================================")
            print(f"PIPELINE {self.name} FAILED - SKIPPING CLEANUP STEPS")
            print(f"========================================================================\n")
            return False
