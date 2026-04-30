import pytest
from datetime import date
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from rareapi.models import RareUser, Category, Post
from rareapi.serializers import ProfileDetailSerializer


class MockRequest:
    def __init__(self, user):
        self.user = user


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def viewer(db):
    return RareUser.objects.create_user(
        username='viewer', password='x', is_active=True,
    )


@pytest.fixture
def author(db):
    return RareUser.objects.create_user(
        username='author', password='x', is_active=True,
    )


@pytest.fixture
def category(db):
    return Category.objects.create(label='General')


@pytest.fixture
def auth_client(api_client, viewer):
    token = Token.objects.create(user=viewer)
    api_client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    return api_client


def make_post(user, category, approved=True):
    return Post.objects.create(
        user=user,
        category=category,
        title='Test Post',
        publication_date=date.today(),
        content='Some content',
        approved=approved,
    )


class TestPostCountSerializer:
    def test_returns_zero_when_user_has_no_posts(self, viewer, author):
        data = ProfileDetailSerializer(author, context={'request': MockRequest(viewer)}).data
        assert data['post_count'] == 0

    def test_counts_approved_posts(self, viewer, author, category):
        make_post(author, category, approved=True)
        make_post(author, category, approved=True)
        data = ProfileDetailSerializer(author, context={'request': MockRequest(viewer)}).data
        assert data['post_count'] == 2

    def test_excludes_unapproved_posts(self, viewer, author, category):
        make_post(author, category, approved=True)
        make_post(author, category, approved=False)
        data = ProfileDetailSerializer(author, context={'request': MockRequest(viewer)}).data
        assert data['post_count'] == 1

    def test_excludes_posts_from_other_users(self, viewer, author, category):
        make_post(viewer, category, approved=True)
        make_post(viewer, category, approved=True)
        data = ProfileDetailSerializer(author, context={'request': MockRequest(viewer)}).data
        assert data['post_count'] == 0

    def test_all_unapproved_posts_yields_zero(self, viewer, author, category):
        make_post(author, category, approved=False)
        make_post(author, category, approved=False)
        data = ProfileDetailSerializer(author, context={'request': MockRequest(viewer)}).data
        assert data['post_count'] == 0


class TestProfileDetailEndpoint:
    def test_post_count_present_in_response(self, auth_client, author):
        response = auth_client.get(f'/profiles/{author.pk}')
        assert response.status_code == 200
        assert 'post_count' in response.json()

    def test_post_count_is_zero_for_new_user(self, auth_client, author):
        response = auth_client.get(f'/profiles/{author.pk}')
        assert response.json()['post_count'] == 0

    def test_post_count_reflects_approved_posts_only(self, auth_client, author, category):
        make_post(author, category, approved=True)
        make_post(author, category, approved=True)
        make_post(author, category, approved=False)
        response = auth_client.get(f'/profiles/{author.pk}')
        assert response.json()['post_count'] == 2

    def test_requires_authentication(self, api_client, author):
        response = api_client.get(f'/profiles/{author.pk}')
        assert response.status_code in (401, 403)

    def test_returns_404_for_nonexistent_user(self, auth_client):
        response = auth_client.get('/profiles/999999')
        assert response.status_code == 404
