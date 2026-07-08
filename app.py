import gradio as gr
import spaces

from progressive_disclosure.app import create_app


@spaces.GPU
def _noop():
    pass


apps = [create_app(tab_name) for tab_name in ("PD", "LGD", "ECL", "Cascade", "Report")]
tab_names = ["PD", "LGD", "ECL", "Cascade", "Report"]

demo = gr.TabbedInterface(
    apps,
    tab_names,
    title="IDBI MSME Risk Assessment",
)


if __name__ == "__main__":
    demo.launch()
