class LoopRefinementAgent:
    """A minimal loop refinement agent stub.

    In the full system this would apply iterative improvements to synthesis
    output; here it simply returns the input unchanged so orchestrator can run.
    """

    def __init__(self):
        pass

    def refine(self, synthesis_output):
        # No-op refinement for now
        return synthesis_output
