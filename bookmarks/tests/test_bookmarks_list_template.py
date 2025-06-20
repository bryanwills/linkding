import datetime
from typing import Type

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.template import Template, RequestContext
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.utils import timezone, formats

from bookmarks.middlewares import LinkdingMiddleware
from bookmarks.models import Bookmark, BookmarkSearch, UserProfile, User
from bookmarks.tests.helpers import BookmarkFactoryMixin, HtmlTestMixin
from bookmarks.views import contexts


class BookmarkListTemplateTest(TestCase, BookmarkFactoryMixin, HtmlTestMixin):

    def assertBookmarksLink(
        self, html: str, bookmark: Bookmark, link_target: str = "_blank"
    ):
        favicon_img = (
            f'<img class="favicon" src="/static/{bookmark.favicon_file}" alt="">'
            if bookmark.favicon_file
            else ""
        )
        self.assertInHTML(
            f"""
            {favicon_img}
            <a href="{bookmark.url}" 
                target="{link_target}" 
                rel="noopener">
                <span>{bookmark.resolved_title}</span>
            </a>
            """,
            html,
        )

    def assertWebArchiveLink(
        self, html: str, label_content: str, url: str, link_target: str = "_blank"
    ):
        self.assertInHTML(
            f"""
        <a href="{url}"
           title="View snapshot on the Internet Archive Wayback Machine" target="{link_target}" rel="noopener">
            {label_content}
        </a>
        """,
            html,
        )

    def assertViewLink(self, html: str, bookmark: Bookmark, base_url=None):
        self.assertViewLinkCount(html, bookmark, base_url)

    def assertNoViewLink(self, html: str, bookmark: Bookmark, base_url=None):
        self.assertViewLinkCount(html, bookmark, base_url, count=0)

    def assertViewLinkCount(
        self,
        html: str,
        bookmark: Bookmark,
        base_url: str = None,
        count=1,
    ):
        if base_url is None:
            base_url = reverse("linkding:bookmarks.index")
        details_url = base_url + f"?details={bookmark.id}"
        self.assertInHTML(
            f"""
                <a href="{details_url}" class="view-action" data-turbo-action="replace" data-turbo-frame="details-modal">View</a>
            """,
            html,
            count=count,
        )

    def assertEditLinkCount(self, html: str, bookmark: Bookmark, count=1):
        edit_url = reverse("linkding:bookmarks.edit", args=[bookmark.id])
        self.assertInHTML(
            f"""
            <a href="{edit_url}?return_url=/bookmarks">Edit</a>
        """,
            html,
            count=count,
        )

    def assertArchiveLinkCount(self, html: str, bookmark: Bookmark, count=1):
        self.assertInHTML(
            f"""
            <button type="submit" name="archive" value="{bookmark.id}"
               class="btn btn-link btn-sm">Archive</button>
        """,
            html,
            count=count,
        )

    def assertDeleteLinkCount(self, html: str, bookmark: Bookmark, count=1):
        self.assertInHTML(
            f"""
            <button ld-confirm-button type="submit" name="remove" value="{bookmark.id}"
               class="btn btn-link btn-sm">Remove</button>
        """,
            html,
            count=count,
        )

    def assertBookmarkActions(self, html: str, bookmark: Bookmark):
        self.assertBookmarkActionsCount(html, bookmark, count=1)

    def assertNoBookmarkActions(self, html: str, bookmark: Bookmark):
        self.assertBookmarkActionsCount(html, bookmark, count=0)

    def assertBookmarkActionsCount(self, html: str, bookmark: Bookmark, count=1):
        self.assertEditLinkCount(html, bookmark, count=count)
        self.assertArchiveLinkCount(html, bookmark, count=count)
        self.assertDeleteLinkCount(html, bookmark, count=count)

    def assertShareInfo(self, html: str, bookmark: Bookmark):
        self.assertShareInfoCount(html, bookmark, 1)

    def assertNoShareInfo(self, html: str, bookmark: Bookmark):
        self.assertShareInfoCount(html, bookmark, 0)

    def assertShareInfoCount(self, html: str, bookmark: Bookmark, count=1):
        # Shared by link
        self.assertInHTML(
            f"""
            <span>Shared by 
                <a href="?user={bookmark.owner.username}">{bookmark.owner.username}</a>
            </span>
        """,
            html,
            count=count,
        )

    def assertFaviconVisible(self, html: str, bookmark: Bookmark):
        self.assertFavicon(html, bookmark, True)

    def assertFaviconHidden(self, html: str, bookmark: Bookmark):
        self.assertFavicon(html, bookmark, False)

    def assertFavicon(self, html: str, bookmark: Bookmark, visible=True):
        soup = self.make_soup(html)

        favicon = soup.select_one(".favicon")

        if not visible:
            self.assertIsNone(favicon)
            return

        url = f"/static/{bookmark.favicon_file}"
        self.assertIsNotNone(favicon)
        self.assertEqual(favicon["src"], url)

    def assertPreviewImageVisible(self, html: str, bookmark: Bookmark):
        self.assertPreviewImage(html, bookmark, True)

    def assertPreviewImageHidden(self, html: str, bookmark: Bookmark):
        self.assertPreviewImage(html, bookmark, False)

    def assertPreviewImage(self, html: str, bookmark: Bookmark, visible=True):
        soup = self.make_soup(html)
        preview_image = soup.select_one(".preview-image")

        if not visible:
            self.assertIsNone(preview_image)
            return

        url = f"/static/{bookmark.preview_image_file}"
        self.assertIsNotNone(preview_image)
        self.assertEqual(preview_image["src"], url)

    def assertPreviewImagePlaceholder(self, html: str):
        soup = self.make_soup(html)
        placeholder = soup.select_one(".preview-image.placeholder")
        self.assertIsNotNone(placeholder)

    def assertBookmarkURLCount(
        self, html: str, bookmark: Bookmark, link_target: str = "_blank", count=0
    ):
        self.assertInHTML(
            f"""
        <div class="url-path truncate">
          <a href="{bookmark.url}" target="{link_target}" rel="noopener" 
          class="url-display">
            {bookmark.url}
          </a>
        </div>
        """,
            html,
            count,
        )

    def assertBookmarkURLVisible(self, html: str, bookmark: Bookmark):
        self.assertBookmarkURLCount(html, bookmark, count=1)

    def assertBookmarkURLHidden(
        self, html: str, bookmark: Bookmark, link_target: str = "_blank"
    ):
        self.assertBookmarkURLCount(html, bookmark, count=0)

    def assertNotes(self, html: str, notes_html: str, count=1):
        self.assertInHTML(
            f"""
        <div class="notes">
          <div class="markdown">
            {notes_html}
          </div>
        </div>
        """,
            html,
            count=count,
        )

    def assertNotesToggle(self, html: str, count=1):
        self.assertInHTML(
            """
        <button type="button" class="btn btn-link btn-sm btn-icon toggle-notes">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">
            <use xlink:href="#ld-icon-note"></use>
          </svg>
          Notes
        </button>      
          """,
            html,
            count=count,
        )

    def assertUnshareButton(self, html: str, bookmark: Bookmark, count=1):
        self.assertInHTML(
            f"""
        <button type="submit" name="unshare" value="{bookmark.id}"
                class="btn btn-link btn-sm btn-icon"
                ld-confirm-button ld-confirm-icon="ld-icon-unshare" ld-confirm-question="Unshare?">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">
            <use xlink:href="#ld-icon-share"></use>
          </svg>
          Shared
        </button>    
          """,
            html,
            count=count,
        )

    def assertMarkAsReadButton(self, html: str, bookmark: Bookmark, count=1):
        self.assertInHTML(
            f"""
        <button type="submit" name="mark_as_read" value="{bookmark.id}"
                class="btn btn-link btn-sm btn-icon"
                ld-confirm-button ld-confirm-icon="ld-icon-read" ld-confirm-question="Mark as read?">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">
            <use xlink:href="#ld-icon-unread"></use>
          </svg>
          Unread
        </button>   
          """,
            html,
            count=count,
        )

    def render_template(
        self,
        url="/bookmarks",
        context_type: Type[
            contexts.BookmarkListContext
        ] = contexts.ActiveBookmarkListContext,
        user: User | AnonymousUser = None,
        is_preview: bool = False,
    ) -> str:
        rf = RequestFactory()
        request = rf.get(url)
        request.user = user or self.get_or_create_test_user()
        middleware = LinkdingMiddleware(lambda r: HttpResponse())
        middleware(request)

        search = BookmarkSearch.from_request(request, request.GET)
        bookmark_list_context = context_type(request, search)
        if is_preview:
            bookmark_list_context.is_preview = True
        context = RequestContext(request, {"bookmark_list": bookmark_list_context})

        template = Template("{% include 'bookmarks/bookmark_list.html' %}")
        return template.render(context)

    def setup_date_format_test(
        self, date_display_setting: str, web_archive_url: str = ""
    ):
        bookmark = self.setup_bookmark()
        bookmark.date_added = timezone.now() - relativedelta(days=8)
        bookmark.web_archive_snapshot_url = web_archive_url
        bookmark.save()
        user = self.get_or_create_test_user()
        user.profile.bookmark_date_display = date_display_setting
        user.profile.save()
        return bookmark

    def inline_bookmark_description_test(self, bookmark):
        html = self.render_template()
        soup = self.make_soup(html)

        has_description = bool(bookmark.description)
        has_tags = len(bookmark.tags.all()) > 0

        # inline description block exists
        description = soup.select_one(".description.inline.truncate")
        self.assertIsNotNone(description)

        # separate description block does not exist
        separate_description = soup.select_one(".description.separate")
        self.assertIsNone(separate_description)

        # one direct child element per description or tags
        children = description.find_all(recursive=False)
        expected_child_count = (
            0 + (1 if has_description else 0) + (1 if has_tags else 0)
        )
        self.assertEqual(len(children), expected_child_count)

        # has separator between description and tags
        if has_description and has_tags:
            self.assertTrue("|" in description.text)

        # contains description text, without leading/trailing whitespace
        if has_description:
            description_text = description.find("span", string=bookmark.description)
            self.assertIsNotNone(description_text)

        if not has_tags:
            # no tags element
            tags = soup.select_one(".tags")
            self.assertIsNone(tags)
        else:
            # tags element exists
            tags = soup.select_one(".tags")
            self.assertIsNotNone(tags)

            # one link for each tag
            tag_links = tags.find_all("a")
            self.assertEqual(len(tag_links), len(bookmark.tags.all()))

            for tag in bookmark.tags.all():
                tag_link = tags.find("a", string=f"#{tag.name}")
                self.assertIsNotNone(tag_link)
                self.assertEqual(tag_link["href"], f"?q=%23{tag.name}")

    def test_inline_bookmark_description(self):
        profile = self.get_or_create_test_user().profile
        profile.bookmark_description_display = (
            UserProfile.BOOKMARK_DESCRIPTION_DISPLAY_INLINE
        )
        profile.save()

        # no description, no tags
        bookmark = self.setup_bookmark(description="")
        self.inline_bookmark_description_test(bookmark)

        # with description, no tags
        bookmark = self.setup_bookmark(description="Test description")
        self.inline_bookmark_description_test(bookmark)

        # no description, with tags
        Bookmark.objects.all().delete()
        bookmark = self.setup_bookmark(
            description="", tags=[self.setup_tag(), self.setup_tag(), self.setup_tag()]
        )
        self.inline_bookmark_description_test(bookmark)

        # with description, with tags
        Bookmark.objects.all().delete()
        bookmark = self.setup_bookmark(
            description="Test description",
            tags=[self.setup_tag(), self.setup_tag(), self.setup_tag()],
        )
        self.inline_bookmark_description_test(bookmark)

    def separate_bookmark_description_test(self, bookmark):
        html = self.render_template()
        soup = self.make_soup(html)

        has_description = bool(bookmark.description)
        has_tags = len(bookmark.tags.all()) > 0

        # inline description block does not exist
        inline_description = soup.select_one(".description.inline")
        self.assertIsNone(inline_description)

        if not has_description:
            # no description element
            description = soup.select_one(".description")
            self.assertIsNone(description)
        else:
            # contains description text, without leading/trailing whitespace
            description = soup.select_one(".description.separate")
            self.assertIsNotNone(description)
            self.assertEqual(description.text, bookmark.description)

        if not has_tags:
            # no tags element
            tags = soup.select_one(".tags")
            self.assertIsNone(tags)
        else:
            # tags element exists
            tags = soup.select_one(".tags")
            self.assertIsNotNone(tags)

            # one link for each tag
            tag_links = tags.find_all("a")
            self.assertEqual(len(tag_links), len(bookmark.tags.all()))

            for tag in bookmark.tags.all():
                tag_link = tags.find("a", string=f"#{tag.name}")
                self.assertIsNotNone(tag_link)
                self.assertEqual(tag_link["href"], f"?q=%23{tag.name}")

    def test_separate_bookmark_description(self):
        profile = self.get_or_create_test_user().profile
        profile.bookmark_description_display = (
            UserProfile.BOOKMARK_DESCRIPTION_DISPLAY_SEPARATE
        )
        profile.save()

        # no description, no tags
        bookmark = self.setup_bookmark(description="")
        self.separate_bookmark_description_test(bookmark)

        # with description, no tags
        bookmark = self.setup_bookmark(description="Test description")
        self.separate_bookmark_description_test(bookmark)

        # no description, with tags
        Bookmark.objects.all().delete()
        bookmark = self.setup_bookmark(
            description="", tags=[self.setup_tag(), self.setup_tag(), self.setup_tag()]
        )
        self.separate_bookmark_description_test(bookmark)

        # with description, with tags
        Bookmark.objects.all().delete()
        bookmark = self.setup_bookmark(
            description="Test description",
            tags=[self.setup_tag(), self.setup_tag(), self.setup_tag()],
        )
        self.separate_bookmark_description_test(bookmark)

    def test_bookmark_description_max_lines(self):
        self.setup_bookmark()
        html = self.render_template()
        soup = self.make_soup(html)
        bookmark_list = soup.select_one("ul.bookmark-list")
        style = bookmark_list["style"]
        self.assertIn("--ld-bookmark-description-max-lines:1;", style)

        profile = self.get_or_create_test_user().profile
        profile.bookmark_description_max_lines = 3
        profile.save()

        html = self.render_template()
        soup = self.make_soup(html)
        bookmark_list = soup.select_one("ul.bookmark-list")
        style = bookmark_list["style"]
        self.assertIn("--ld-bookmark-description-max-lines:3;", style)

    def test_bookmark_tag_ordering(self):
        bookmark = self.setup_bookmark()
        tag3 = self.setup_tag(name="tag3")
        tag1 = self.setup_tag(name="tag1")
        tag2 = self.setup_tag(name="tag2")
        bookmark.tags.add(tag3, tag1, tag2)

        html = self.render_template()
        soup = self.make_soup(html)
        tags = soup.select_one(".tags")
        tag_links = tags.find_all("a")
        self.assertEqual(len(tag_links), 3)
        self.assertEqual(tag_links[0].text, "#tag1")
        self.assertEqual(tag_links[1].text, "#tag2")
        self.assertEqual(tag_links[2].text, "#tag3")

    def test_should_render_web_archive_link_with_absolute_date_setting(self):
        bookmark = self.setup_date_format_test(
            UserProfile.BOOKMARK_DATE_DISPLAY_ABSOLUTE,
            "https://web.archive.org/web/20210811214511/https://wanikani.com/",
        )
        html = self.render_template()
        formatted_date = formats.date_format(bookmark.date_added, "SHORT_DATE_FORMAT")

        self.assertWebArchiveLink(
            html, formatted_date, bookmark.web_archive_snapshot_url
        )

    def test_should_render_web_archive_link_with_relative_date_setting(self):
        bookmark = self.setup_date_format_test(
            UserProfile.BOOKMARK_DATE_DISPLAY_RELATIVE,
            "https://web.archive.org/web/20210811214511/https://wanikani.com/",
        )
        html = self.render_template()

        self.assertWebArchiveLink(html, "1 week ago", bookmark.web_archive_snapshot_url)

    def test_should_render_generated_web_archive_link_without_saved_snapshot_url(self):
        user = self.get_or_create_test_user()
        user.profile.bookmark_date_display = UserProfile.BOOKMARK_DATE_DISPLAY_ABSOLUTE
        user.profile.save()

        date_added = timezone.datetime(
            2023, 8, 11, 21, 45, 11, tzinfo=datetime.timezone.utc
        )
        bookmark = self.setup_bookmark(
            url="https://example.com/article", added=date_added
        )

        html = self.render_template()
        formatted_date = formats.date_format(bookmark.date_added, "SHORT_DATE_FORMAT")

        self.assertWebArchiveLink(
            html,
            formatted_date,
            "https://web.archive.org/web/20230811214511/https://example.com/article",
        )

    def test_bookmark_link_target_should_be_blank_by_default(self):
        bookmark = self.setup_bookmark()
        html = self.render_template()

        self.assertBookmarksLink(html, bookmark, link_target="_blank")

    def test_bookmark_link_target_should_respect_user_profile(self):
        profile = self.get_or_create_test_user().profile
        profile.bookmark_link_target = UserProfile.BOOKMARK_LINK_TARGET_SELF
        profile.save()

        bookmark = self.setup_bookmark()
        html = self.render_template()

        self.assertBookmarksLink(html, bookmark, link_target="_self")

    def test_web_archive_link_target_should_be_blank_by_default(self):
        bookmark = self.setup_bookmark()
        bookmark.date_added = timezone.now() - relativedelta(days=8)
        bookmark.web_archive_snapshot_url = "https://example.com"
        bookmark.save()

        html = self.render_template()

        self.assertWebArchiveLink(
            html, "1 week ago", bookmark.web_archive_snapshot_url, link_target="_blank"
        )

    def test_web_archive_link_target_should_respect_user_profile(self):
        profile = self.get_or_create_test_user().profile
        profile.bookmark_link_target = UserProfile.BOOKMARK_LINK_TARGET_SELF
        profile.save()

        bookmark = self.setup_bookmark()
        bookmark.date_added = timezone.now() - relativedelta(days=8)
        bookmark.web_archive_snapshot_url = "https://example.com"
        bookmark.save()

        html = self.render_template()

        self.assertWebArchiveLink(
            html, "1 week ago", bookmark.web_archive_snapshot_url, link_target="_self"
        )

    def test_should_render_latest_snapshot_link_if_one_exists(self):
        bookmark = self.setup_date_format_test(
            UserProfile.BOOKMARK_DATE_DISPLAY_ABSOLUTE
        )
        bookmark.latest_snapshot = self.setup_asset(bookmark)
        bookmark.save()

        html = self.render_template()
        formatted_date = formats.date_format(bookmark.date_added, "SHORT_DATE_FORMAT")
        snapshot_url = reverse(
            "linkding:assets.view", args=[bookmark.latest_snapshot.id]
        )

        # Check that the snapshot link is rendered with the correct URL and title
        self.assertInHTML(
            f"""
            <a href="{snapshot_url}"
               title="View latest snapshot" target="_blank" rel="noopener">
                {formatted_date}
            </a>
            <span>|</span>
            """,
            html,
        )

    def test_should_reflect_unread_state_as_css_class(self):
        self.setup_bookmark(unread=True)
        html = self.render_template()
        soup = self.make_soup(html)

        list_item = soup.select_one("li[ld-bookmark-item]")
        self.assertIsNotNone(list_item)
        self.assertListEqual(["unread"], list_item["class"])

    def test_should_reflect_shared_state_as_css_class(self):
        profile = self.get_or_create_test_user().profile
        profile.enable_sharing = True
        profile.save()

        self.setup_bookmark(shared=True)
        html = self.render_template()
        soup = self.make_soup(html)

        list_item = soup.select_one("li[ld-bookmark-item]")
        self.assertIsNotNone(list_item)
        self.assertListEqual(["shared"], list_item["class"])

    def test_should_reflect_both_unread_and_shared_state_as_css_class(self):
        profile = self.get_or_create_test_user().profile
        profile.enable_sharing = True
        profile.save()

        self.setup_bookmark(unread=True, shared=True)
        html = self.render_template()
        soup = self.make_soup(html)

        list_item = soup.select_one("li[ld-bookmark-item]")
        self.assertIsNotNone(list_item)
        self.assertListEqual(["unread", "shared"], list_item["class"])

    def test_show_bookmark_actions_for_owned_bookmarks(self):
        bookmark = self.setup_bookmark()
        html = self.render_template()

        self.assertViewLink(html, bookmark)
        self.assertBookmarkActions(html, bookmark)
        self.assertNoShareInfo(html, bookmark)

    def test_hide_view_link(self):
        bookmark = self.setup_bookmark()
        profile = self.get_or_create_test_user().profile
        profile.display_view_bookmark_action = False
        profile.save()

        html = self.render_template()
        self.assertViewLinkCount(html, bookmark, count=0)
        self.assertEditLinkCount(html, bookmark, count=1)
        self.assertArchiveLinkCount(html, bookmark, count=1)
        self.assertDeleteLinkCount(html, bookmark, count=1)

    def test_hide_edit_link(self):
        bookmark = self.setup_bookmark()
        profile = self.get_or_create_test_user().profile
        profile.display_edit_bookmark_action = False
        profile.save()

        html = self.render_template()
        self.assertViewLinkCount(html, bookmark, count=1)
        self.assertEditLinkCount(html, bookmark, count=0)
        self.assertArchiveLinkCount(html, bookmark, count=1)
        self.assertDeleteLinkCount(html, bookmark, count=1)

    def test_hide_archive_link(self):
        bookmark = self.setup_bookmark()
        profile = self.get_or_create_test_user().profile
        profile.display_archive_bookmark_action = False
        profile.save()

        html = self.render_template()
        self.assertViewLinkCount(html, bookmark, count=1)
        self.assertEditLinkCount(html, bookmark, count=1)
        self.assertArchiveLinkCount(html, bookmark, count=0)
        self.assertDeleteLinkCount(html, bookmark, count=1)

    def test_hide_remove_link(self):
        bookmark = self.setup_bookmark()
        profile = self.get_or_create_test_user().profile
        profile.display_remove_bookmark_action = False
        profile.save()

        html = self.render_template()
        self.assertViewLinkCount(html, bookmark, count=1)
        self.assertEditLinkCount(html, bookmark, count=1)
        self.assertArchiveLinkCount(html, bookmark, count=1)
        self.assertDeleteLinkCount(html, bookmark, count=0)

    def test_show_share_info_for_non_owned_bookmarks(self):
        other_user = User.objects.create_user(
            "otheruser", "otheruser@example.com", "password123"
        )
        other_user.profile.enable_sharing = True
        other_user.profile.save()

        bookmark = self.setup_bookmark(user=other_user, shared=True)
        html = self.render_template(context_type=contexts.SharedBookmarkListContext)

        self.assertViewLink(
            html, bookmark, base_url=reverse("linkding:bookmarks.shared")
        )
        self.assertNoBookmarkActions(html, bookmark)
        self.assertShareInfo(html, bookmark)

    def test_share_info_user_link_keeps_query_params(self):
        other_user = User.objects.create_user(
            "otheruser", "otheruser@example.com", "password123"
        )
        other_user.profile.enable_sharing = True
        other_user.profile.save()

        bookmark = self.setup_bookmark(user=other_user, shared=True, title="foo")
        html = self.render_template(
            url="/bookmarks?q=foo", context_type=contexts.SharedBookmarkListContext
        )

        self.assertInHTML(
            f"""
            <span>Shared by 
                <a href="?q=foo&user={bookmark.owner.username}">{bookmark.owner.username}</a>
            </span>
        """,
            html,
        )

    def test_preview_image_should_be_visible_when_preview_images_enabled(self):
        profile = self.get_or_create_test_user().profile
        profile.enable_preview_images = True
        profile.save()

        bookmark = self.setup_bookmark(preview_image_file="preview.png")
        html = self.render_template()

        self.assertPreviewImageVisible(html, bookmark)

    def test_preview_image_should_be_hidden_when_preview_images_disabled(self):
        profile = self.get_or_create_test_user().profile
        profile.enable_preview_images = False
        profile.save()

        bookmark = self.setup_bookmark(preview_image_file="preview.png")
        html = self.render_template()

        self.assertPreviewImageHidden(html, bookmark)

    def test_preview_image_shows_placeholder_when_there_is_no_preview_image(self):
        profile = self.get_or_create_test_user().profile
        profile.enable_preview_images = True
        profile.save()

        self.setup_bookmark()
        html = self.render_template()

        self.assertPreviewImagePlaceholder(html)

    def test_favicon_should_be_visible_when_favicons_enabled(self):
        profile = self.get_or_create_test_user().profile
        profile.enable_favicons = True
        profile.save()

        bookmark = self.setup_bookmark(favicon_file="https_example_com.png")
        html = self.render_template()

        self.assertFaviconVisible(html, bookmark)

    def test_favicon_should_be_hidden_when_there_is_no_icon(self):
        profile = self.get_or_create_test_user().profile
        profile.enable_favicons = True
        profile.save()

        bookmark = self.setup_bookmark(favicon_file="")
        html = self.render_template()

        self.assertFaviconHidden(html, bookmark)

    def test_favicon_should_be_hidden_when_favicons_disabled(self):
        profile = self.get_or_create_test_user().profile
        profile.enable_favicons = False
        profile.save()

        bookmark = self.setup_bookmark(favicon_file="https_example_com.png")
        html = self.render_template()

        self.assertFaviconHidden(html, bookmark)

    def test_bookmark_url_should_be_hidden_by_default(self):
        profile = self.get_or_create_test_user().profile
        profile.save()

        bookmark = self.setup_bookmark()
        html = self.render_template()

        self.assertBookmarkURLHidden(html, bookmark)

    def test_show_bookmark_url_when_enabled(self):
        profile = self.get_or_create_test_user().profile
        profile.display_url = True
        profile.save()

        bookmark = self.setup_bookmark()
        html = self.render_template()

        self.assertBookmarkURLVisible(html, bookmark)

    def test_hide_bookmark_url_when_disabled(self):
        profile = self.get_or_create_test_user().profile
        profile.display_url = False
        profile.save()

        bookmark = self.setup_bookmark()
        html = self.render_template()

        self.assertBookmarkURLHidden(html, bookmark)

    def test_show_mark_as_read_when_unread(self):
        bookmark = self.setup_bookmark(unread=True)
        html = self.render_template()

        self.assertMarkAsReadButton(html, bookmark)

    def test_hide_mark_as_read_when_read(self):
        bookmark = self.setup_bookmark(unread=False)
        html = self.render_template()

        self.assertMarkAsReadButton(html, bookmark, count=0)

    def test_hide_mark_as_read_for_non_owned_bookmarks(self):
        other_user = self.setup_user(enable_sharing=True)

        bookmark = self.setup_bookmark(user=other_user, shared=True, unread=True)
        html = self.render_template(context_type=contexts.SharedBookmarkListContext)

        self.assertBookmarksLink(html, bookmark)
        self.assertMarkAsReadButton(html, bookmark, count=0)

    def test_show_unshare_button_when_shared(self):
        profile = self.get_or_create_test_user().profile
        profile.enable_sharing = True
        profile.save()

        bookmark = self.setup_bookmark(shared=True)
        html = self.render_template()

        self.assertUnshareButton(html, bookmark)

    def test_hide_unshare_button_when_not_shared(self):
        profile = self.get_or_create_test_user().profile
        profile.enable_sharing = True
        profile.save()

        bookmark = self.setup_bookmark(shared=False)
        html = self.render_template()

        self.assertUnshareButton(html, bookmark, count=0)

    def test_hide_unshare_button_when_sharing_is_disabled(self):
        profile = self.get_or_create_test_user().profile
        profile.enable_sharing = False
        profile.save()

        bookmark = self.setup_bookmark(shared=True)
        html = self.render_template()

        self.assertUnshareButton(html, bookmark, count=0)

    def test_hide_unshare_for_non_owned_bookmarks(self):
        other_user = self.setup_user(enable_sharing=True)

        bookmark = self.setup_bookmark(user=other_user, shared=True)
        html = self.render_template(context_type=contexts.SharedBookmarkListContext)

        self.assertBookmarksLink(html, bookmark)
        self.assertUnshareButton(html, bookmark, count=0)

    def test_without_notes(self):
        self.setup_bookmark()
        html = self.render_template()

        self.assertNotes(html, "", 0)
        self.assertNotesToggle(html, 0)

    def test_with_notes(self):
        self.setup_bookmark(notes="Test note")
        html = self.render_template()

        note_html = "<p>Test note</p>"
        self.assertNotes(html, note_html, 1)

    def test_note_renders_markdown(self):
        self.setup_bookmark(notes='**Example:** `print("Hello world!")`')
        html = self.render_template()

        note_html = (
            '<p><strong>Example:</strong> <code>print("Hello world!")</code></p>'
        )
        self.assertNotes(html, note_html, 1)

    def test_note_renders_markdown_with_linkify(self):
        # Should linkify plain URL
        self.setup_bookmark(notes="Example: https://example.com")
        html = self.render_template()

        note_html = '<p>Example: <a href="https://example.com" rel="nofollow">https://example.com</a></p>'
        self.assertNotes(html, note_html, 1)

        # Should not linkify URL in markdown link
        self.setup_bookmark(notes="[https://example.com](https://example.com)")
        html = self.render_template()

        note_html = '<p><a href="https://example.com" rel="nofollow">https://example.com</a></p>'
        self.assertNotes(html, note_html, 1)

    def test_note_cleans_html(self):
        self.setup_bookmark(notes='<script>alert("test")</script>')
        self.setup_bookmark(
            notes='<b ld-fetch="https://example.com" ld-on="click">bold text</b>'
        )
        html = self.render_template()

        note_html = '&lt;script&gt;alert("test")&lt;/script&gt;'
        self.assertIn(note_html, html, 1)

        note_html = "<b>bold text</b>"
        self.assertIn(note_html, html, 1)

    def test_notes_are_hidden_initially_by_default(self):
        self.setup_bookmark(notes="Test note")
        html = self.render_template()
        soup = self.make_soup(html)
        bookmark_list = soup.select_one("ul.bookmark-list.show-notes")

        self.assertIsNone(bookmark_list)

    def test_notes_are_hidden_initially_with_permanent_notes_disabled(self):
        profile = self.get_or_create_test_user().profile
        profile.permanent_notes = False
        profile.save()

        self.setup_bookmark(notes="Test note")
        html = self.render_template()
        soup = self.make_soup(html)
        bookmark_list = soup.select_one("ul.bookmark-list.show-notes")

        self.assertIsNone(bookmark_list)

    def test_notes_are_visible_initially_with_permanent_notes_enabled(self):
        profile = self.get_or_create_test_user().profile
        profile.permanent_notes = True
        profile.save()

        self.setup_bookmark(notes="Test note")
        html = self.render_template()
        soup = self.make_soup(html)
        bookmark_list = soup.select_one("ul.bookmark-list.show-notes")

        self.assertIsNotNone(bookmark_list)

    def test_toggle_notes_is_visible_by_default(self):
        self.setup_bookmark(notes="Test note")
        html = self.render_template()

        self.assertNotesToggle(html, 1)

    def test_toggle_notes_is_visible_with_permanent_notes_disabled(self):
        profile = self.get_or_create_test_user().profile
        profile.permanent_notes = False
        profile.save()

        self.setup_bookmark(notes="Test note")
        html = self.render_template()

        self.assertNotesToggle(html, 1)

    def test_toggle_notes_is_hidden_with_permanent_notes_enabled(self):
        profile = self.get_or_create_test_user().profile
        profile.permanent_notes = True
        profile.save()

        self.setup_bookmark(notes="Test note")
        html = self.render_template()

        self.assertNotesToggle(html, 0)

    def test_with_anonymous_user(self):
        profile = self.get_or_create_test_user().profile
        profile.enable_sharing = True
        profile.enable_public_sharing = True
        profile.save()

        bookmark = self.setup_bookmark()
        bookmark.date_added = timezone.now() - relativedelta(days=8)
        bookmark.web_archive_snapshot_url = (
            "https://web.archive.org/web/20230531200136/https://example.com"
        )
        bookmark.notes = '**Example:** `print("Hello world!")`'
        bookmark.favicon_file = "https_example_com.png"
        bookmark.shared = True
        bookmark.unread = True
        bookmark.save()

        html = self.render_template(
            context_type=contexts.SharedBookmarkListContext, user=AnonymousUser()
        )
        self.assertBookmarksLink(html, bookmark, link_target="_blank")
        self.assertWebArchiveLink(
            html, "1 week ago", bookmark.web_archive_snapshot_url, link_target="_blank"
        )
        self.assertViewLink(
            html, bookmark, base_url=reverse("linkding:bookmarks.shared")
        )
        self.assertNoBookmarkActions(html, bookmark)
        self.assertShareInfo(html, bookmark)
        self.assertMarkAsReadButton(html, bookmark, count=0)
        self.assertUnshareButton(html, bookmark, count=0)
        note_html = (
            '<p><strong>Example:</strong> <code>print("Hello world!")</code></p>'
        )
        self.assertNotes(html, note_html, 1)
        self.assertFaviconVisible(html, bookmark)

    def test_empty_state(self):
        html = self.render_template()

        self.assertInHTML(
            '<p class="empty-title h5">You have no bookmarks yet</p>', html
        )

    def test_pagination_is_not_sticky_by_default(self):
        self.setup_bookmark()
        html = self.render_template()

        self.assertIn('<div class="bookmark-pagination">', html)

    def test_pagination_is_sticky_when_enabled_in_profile(self):
        self.setup_bookmark()
        profile = self.get_or_create_test_user().profile
        profile.sticky_pagination = True
        profile.save()
        html = self.render_template()

        self.assertIn('<div class="bookmark-pagination sticky">', html)

    def test_items_per_page_is_30_by_default(self):
        self.setup_numbered_bookmarks(50)
        html = self.render_template()

        soup = self.make_soup(html)
        bookmarks = soup.select("li[ld-bookmark-item]")
        self.assertEqual(30, len(bookmarks))

    def test_items_per_page_is_configurable(self):
        self.setup_numbered_bookmarks(50)
        profile = self.get_or_create_test_user().profile
        profile.items_per_page = 10
        profile.save()
        html = self.render_template()

        soup = self.make_soup(html)
        bookmarks = soup.select("li[ld-bookmark-item]")
        self.assertEqual(10, len(bookmarks))

    def test_no_actions_rendered_when_is_preview(self):
        bookmark = self.setup_bookmark()
        bookmark.date_added = timezone.now() - relativedelta(days=8)
        bookmark.web_archive_snapshot_url = "https://example.com"
        bookmark.save()

        html = self.render_template(is_preview=True)

        # Verify no actions are rendered
        self.assertNoViewLink(html, bookmark)
        self.assertNoBookmarkActions(html, bookmark)
        self.assertMarkAsReadButton(html, bookmark, count=0)
        self.assertUnshareButton(html, bookmark, count=0)
        self.assertNotesToggle(html, count=0)

        # But date should still be rendered
        self.assertWebArchiveLink(html, "1 week ago", bookmark.web_archive_snapshot_url)
