"""Few-shot example scenes injected into the codegen system prompt.

Each string is a complete, correct Manim scene that would pass `sanitize()`
for the scene id matching its position (index 0 -> Scene1, etc). They exist
to anchor the model's style — especially the labeled-row layout, which is
where generated scenes fail most often.
"""

EXAMPLES = [
    '''from manim import *


class Scene1(Scene):
    def construct(self):
        title = Text("How Binary Search Works", font_size=44)
        subtitle = Text("Finding a value in a sorted list", font_size=28, color=GRAY)
        subtitle.next_to(title, DOWN, buff=0.4)

        self.play(Write(title))
        self.play(FadeIn(subtitle))
        self.wait(1)
''',
    '''from manim import *


class Scene2(Scene):
    def construct(self):
        values = [3, 7, 12, 18, 24, 31, 40]

        squares = VGroup(*[Square(side_length=0.8) for _ in values])
        squares.arrange(RIGHT, buff=0.15)
        squares.to_edge(UP, buff=1.5)

        labels = VGroup(*[
            Text(str(value), font_size=24).move_to(square)
            for value, square in zip(values, squares)
        ])

        indices = VGroup(*[
            Text(str(i), font_size=20, color=GRAY).next_to(square, DOWN, buff=0.2)
            for i, square in enumerate(squares)
        ])

        self.play(FadeIn(squares), FadeIn(labels), FadeIn(indices))
        self.wait(1)
''',
    '''from manim import *


class Scene3(Scene):
    def construct(self):
        title = Text("Rate of Change", font_size=40).to_edge(UP)
        self.play(Write(title))

        axes = Axes(
            x_range=[-3, 3, 1],
            y_range=[-1, 9, 2],
            x_length=6,
            y_length=4,
        )
        curve = axes.plot(lambda x: x**2, color=BLUE)
        self.play(FadeIn(axes), Create(curve))
        self.wait(1)

        self.play(FadeOut(axes), FadeOut(curve), FadeOut(title))

        formula = MathTex(r"f(x) = x^2").to_edge(UP)
        derivative = MathTex(r"f'(x) = 2x").next_to(formula, DOWN, buff=0.5)
        self.play(Write(formula))
        self.play(Write(derivative))
        self.wait(1)
''',
]
