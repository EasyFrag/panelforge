"""Keep reference pixels intact before the versioned H3 graph sizes them."""
from .qwen_edit_images import PillowQwenEditImages


class PillowMinimaxEditImages(PillowQwenEditImages):
    def prepare(self, content, dimensions):
        # The baseline's nearest-exact 1 MP preprocessing lives in the workflow.
        return self.normalize_source(content)

    def prepare_guide(self, source, mask, dimensions):
        return super().prepare_guide(source, mask, self.dimensions(source))
