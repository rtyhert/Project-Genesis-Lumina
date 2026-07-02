import pytest
from emotion_system import EmotionSystem


class TestEmotionSystem:
    def test_initial_state(self):
        es = EmotionSystem()
        emo, intens = es.get_dominant_emotion()
        assert emo == "neutral"
        assert intens > 0

    def test_set_emotion(self):
        es = EmotionSystem()
        es.set_emotion("happy", 0.9)
        emo, _ = es.get_dominant_emotion()
        assert emo == "happy"

    def test_unknown_emotion(self):
        es = EmotionSystem()
        es.set_emotion("unknown", 0.5)
        emo, _ = es.get_dominant_emotion()
        assert emo == "neutral"

    def test_blend_emotion(self):
        es = EmotionSystem({"blend_threshold": 0.3})
        es.blend_emotion("happy", 0.8)
        emo, _ = es.get_dominant_emotion()
        assert emo == "happy"

    def test_get_emotion_vector(self):
        es = EmotionSystem()
        vec = es.get_emotion_vector()
        assert isinstance(vec, dict)
        assert "neutral" in vec
        assert len(vec) == 7

    def test_emotion_tag_parse(self):
        assert EmotionSystem.parse_emotion_tag("[emotion:happy] hello") == "happy"
        assert EmotionSystem.parse_emotion_tag("no tag here") is None

    def test_emotion_tag_strip(self):
        assert EmotionSystem.strip_emotion_tag("[emotion:sad] [emotion:happy] hi") == "hi"
        assert EmotionSystem.strip_emotion_tag("no tag") == "no tag"

    def test_reset(self):
        es = EmotionSystem()
        es.set_emotion("happy", 1.0)
        es.reset()
        emo, _ = es.get_dominant_emotion()
        assert emo == "neutral"

    def test_get_suggested_actions_neutral(self):
        es = EmotionSystem()
        actions = es.get_suggested_actions()
        assert len(actions) > 0
        assert "blink" in actions

    def test_get_suggested_actions_happy(self):
        es = EmotionSystem()
        es.set_emotion("happy", 1.0)
        actions = es.get_suggested_actions()
        assert "smile" in actions or "laugh" in actions or "cheer" in actions

    def test_get_suggested_actions_custom(self):
        action_map = {"happy": ["purr", "tail_wag"], "neutral": ["blink"]}
        es = EmotionSystem(action_map=action_map)
        es.set_emotion("happy", 1.0)
        actions = es.get_suggested_actions()
        assert "purr" in actions
