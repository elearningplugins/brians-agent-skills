"""Tests for true_surface.smooth_surface: it removes spikes without shrinking the solid, keeps held vertices and the bed still, and never leaves a fold."""
import numpy as np
import trimesh

from printcheck import roughness, self_intersections
from true_surface import smooth_surface


def noisy_sphere(seed=0, sigma=0.08):
    m = trimesh.creation.icosphere(subdivisions=5, radius=10.0)
    m.apply_translation([0, 10.0, 0])
    rng = np.random.default_rng(seed)
    m.vertices += m.vertex_normals * rng.normal(0, sigma, len(m.vertices))[:, None]
    return m


def test_smoothing_removes_noise_without_shrinking():
    m = noisy_sphere()
    v, report = smooth_surface(m, passes=5, bed_fade_mm=2.0, folded=lambda t: np.zeros(len(t.faces), bool))
    s = trimesh.Trimesh(v, m.faces, process=False)
    # The bed zone is left as it was on purpose, so judge the vertices smoothing may move, a ring clear of that zone
    free = m.vertices[:, 1] > m.vertices[:, 1].min() + 3.0
    assert np.percentile(roughness(s)[free], 99) < 0.5 * np.percentile(roughness(m)[free], 99)
    assert abs(s.volume - m.volume) / m.volume < 0.005
    assert report["reverted"] == 0


def test_bed_and_held_vertices_stay_put():
    m = noisy_sphere(1)
    near_bed = m.vertices[:, 1] < m.vertices[:, 1].min() + 2.0
    hold = m.vertices[:, 0] > 5.0
    v, _ = smooth_surface(m, passes=5, bed_fade_mm=2.0, folded=lambda t: np.zeros(len(t.faces), bool), hold=hold)
    np.testing.assert_array_equal(v[near_bed], m.vertices[near_bed])
    np.testing.assert_array_equal(v[hold], m.vertices[hold])


def test_vertices_around_a_fold_are_put_back():
    m = noisy_sphere(2)
    watched = m.faces[:40]

    def folded(t):
        # Flags the first 40 faces as folded whenever smoothing has moved any of their corners
        bad = np.zeros(len(t.faces), bool)
        bad[:40] = np.abs(t.vertices[watched] - m.vertices[watched]).max(axis=(1, 2)) > 0
        return bad

    v, report = smooth_surface(m, passes=5, bed_fade_mm=2.0, folded=folded)
    np.testing.assert_array_equal(v[watched], m.vertices[watched])
    assert report["reverted"] > 0
    assert len(self_intersections(trimesh.Trimesh(v, m.faces, process=False))) == 0
