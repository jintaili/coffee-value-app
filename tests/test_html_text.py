from coffee_value_app.html_text import html_to_text


def test_html_to_text_keeps_title_description_and_main_text() -> None:
    html = """
    <html>
      <head>
        <title>Peru La Margarita Gesha</title>
        <meta name="description" content="A washed Gesha from Peru.">
        <script>window.secret = "ignore";</script>
      </head>
      <body>
        <nav>Subscribe Account Cart</nav>
        <main>
          <h1>Peru La Margarita Gesha</h1>
          <p>Jasmine, white grape, black tea.</p>
          <p>$26.00 / 10 oz</p>
        </main>
      </body>
    </html>
    """

    text = html_to_text(html)

    assert "Title: Peru La Margarita Gesha" in text
    assert "Description: A washed Gesha from Peru." in text
    assert "Jasmine, white grape, black tea." in text
    assert "$26.00 / 10 oz" in text
    assert "window.secret" not in text

