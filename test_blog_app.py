import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"


class BlogAppTests(unittest.TestCase):
    def test_article_images_are_unique_canonical_wikimedia_urls(self):
        source = (FRONTEND / "blogs.js").read_text()
        images = re.findall(r'image: "([^"]+)"', source)
        self.assertEqual(len(images), 9)
        self.assertEqual(len(set(images)), 9)
        self.assertTrue(all(url.startswith("https://upload.wikimedia.org/wikipedia/commons/") for url in images))
        self.assertTrue(all("utm_source" not in url for url in images))

    def test_required_files_exist(self):
        for filename in ("index.html", "style.css", "blogs.js", "script.js", "blog.html"):
            self.assertTrue((FRONTEND / filename).exists(), filename)

    def test_nine_articles_are_defined(self):
        source = (FRONTEND / "blogs.js").read_text()
        self.assertEqual(source.count("id:"), 9)
        self.assertEqual(source.count("title:"), 9)
        self.assertEqual(source.count("category:"), 9)
        self.assertEqual(source.count("image:"), 9)
        self.assertEqual(source.count("content:"), 9)

    def test_articles_have_complete_content(self):
        source = (FRONTEND / "blogs.js").read_text()
        for topic in (
            "Road to World Cup 2027",
            "Rohit Sharma",
            "Virat Kohli",
            "Young Cricket Stars",
            "Jasprit Bumrah",
            "Predicted Playing XI",
            "India vs Pakistan",
            "Venues, Schedule and Conditions",
            "World Champions in 2027",
        ):
            self.assertIn(topic, source)

    def test_all_nine_articles_use_verified_wikimedia_images(self):
        source = (FRONTEND / "blogs.js").read_text()
        expected = [
            "https://upload.wikimedia.org/wikipedia/commons/c/ce/Indian_cricket_team.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/3/31/ROHIT_SHARMA.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/7/7e/Virat_Kohli.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/2/29/Shubman_Gill.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/a/ac/Jasprit_Bumrah.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/9/95/Indian_cricket_team_warmup.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/c/c3/Manmohan_Singh_and_the_Prime_Minister_of_Pakistan%2C_Mr._Yousuf_Raza_Gilani_interacting_with_the_Indian_Cricket_Team_at_the_Indo-Pak_World_Cup_semi-final%2C_at_the_Punjab_Cricket_Association_stadium%2C_in_Mohali_on_March_30%2C_2011.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/5/5e/Newlands_Cricket_Ground.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/e/e6/People_celebrating_India%27s_CWC11_win_%288310811320%29.jpg",
        ]
        for image in expected:
            self.assertIn(image, source)

    def test_homepage_has_blog_grid_and_count(self):
        html = (FRONTEND / "index.html").read_text()
        self.assertNotIn('id="searchInput"', html)
        self.assertNotIn('id="categoryFilter"', html)
        self.assertIn('id="blogGrid"', html)
        self.assertIn('id="blogCount"', html)

    def test_nine_articles_are_unique_and_substantive(self):
        source = (FRONTEND / "blogs.js").read_text()
        articles = re.findall(r'content: \[(.*?)\]\s*\n\s*\}', source, re.S)
        self.assertEqual(len(articles), 9)
        self.assertEqual(len(set(articles)), 9)

        for article in articles:
            words = len(re.findall(r"\b[\w'-]+\b", article))
            self.assertGreaterEqual(words, 500)
            self.assertLessEqual(words, 700)
            self.assertIn('## ', article)
            self.assertIn('Key highlight', article)

    def test_contact_section_and_footer_branding(self):
        html = (FRONTEND / "index.html").read_text()
        self.assertIn('id="contact"', html)
        self.assertIn('Contact Team India Cricket Blog', html)
        self.assertIn('mailto:contact@example.com', html)
        self.assertIn('Location: India', html)
        self.assertIn("Have questions, suggestions, or feedback about Indian cricket? We'd love to hear from you!", html)

        footer = (FRONTEND / "index.html").read_text()
        self.assertIn('🇮🇳 Team India – Road to World Cup 2027', footer)
        self.assertIn('© 2026 Team India Cricket Blog. All rights reserved.', footer)
        self.assertNotIn('₹', footer)

    def test_predicted_playing_xi_has_exactly_eleven_cards(self):
        html = (FRONTEND / "index.html").read_text()
        expected = [
            "Rohit Sharma",
            "Shubman Gill",
            "Virat Kohli",
            "Shreyas Iyer",
            "KL Rahul",
            "Hardik Pandya",
            "Ravindra Jadeja",
            "Axar Patel",
            "Kuldeep Yadav",
            "Jasprit Bumrah",
            "Bhuvneshwar Kumar",
        ]
        self.assertIn('India\'s Predicted Playing XI – World Cup 2027', html)
        for name in expected:
            self.assertIn(name, html)
        self.assertNotIn('Mohammed Siraj', html)
        self.assertEqual(html.count('class="player-profile"'), 11)
        self.assertEqual(html.count('class="player-card"'), 11)
        self.assertIn('https://upload.wikimedia.org/wikipedia/commons/8/80/Bhuvneshwar_Kumar.jpg', html)

    def test_blog_detail_page_has_article_container_and_back_link(self):
        html = (FRONTEND / "blog.html").read_text()
        self.assertIn('id="articlePage"', html)
        self.assertIn('id="backToBlogs"', html)
        self.assertIn('id="relatedArticles"', html)

    def test_homepage_and_detail_page_link_to_stylesheet_and_script(self):
        for filename in ("index.html", "blog.html"):
            html = (FRONTEND / filename).read_text()
            self.assertIn('style.css', html)
            self.assertIn('blogs.js', html)
            self.assertIn('script.js', html)

    def test_player_profiles_exist_and_are_internal(self):
        html = (FRONTEND / "index.html").read_text()
        self.assertEqual(html.count('class="player-profile"'), 11)
        self.assertEqual(html.count('href="player-profile.html?player='), 11)
        self.assertNotIn('https://www.espncricinfo.com/cricketers/', html)

    def test_player_profile_page_contains_required_data(self):
        html = (FRONTEND / "player-profile.html").read_text()
        self.assertIn('id="playerProfile"', html)
        self.assertIn('id="backToPlayers"', html)
        self.assertIn('player-profile.js', html)
        self.assertIn('player-profile.css', html)


if __name__ == "__main__":
    unittest.main()
