import math

class SignLanguageEngine:
    """
    Sign Language Recognition Engine based on 21 MediaPipe hand landmarks.
    Analyzes geometric finger states (UP vs DOWN), relative joint distances,
    and spatial vectors to classify ASL alphabets, numbers, and interview phrases.
    """

    LANDMARK_NAMES = [
        "WRIST",
        "THUMB_CMC", "THUMB_MCP", "THUMB_IP", "THUMB_TIP",
        "INDEX_FINGER_MCP", "INDEX_FINGER_PIP", "INDEX_FINGER_DIP", "INDEX_FINGER_TIP",
        "MIDDLE_FINGER_MCP", "MIDDLE_FINGER_PIP", "MIDDLE_FINGER_DIP", "MIDDLE_FINGER_TIP",
        "RING_FINGER_MCP", "RING_FINGER_PIP", "RING_FINGER_DIP", "RING_FINGER_TIP",
        "PINKY_MCP", "PINKY_PIP", "PINKY_DIP", "PINKY_TIP"
    ]

    @staticmethod
    def euclidean_distance(p1, p2):
        dx = p1.get('x', 0) - p2.get('x', 0)
        dy = p1.get('y', 0) - p2.get('y', 0)
        dz = p1.get('z', 0) - p2.get('z', 0)
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    @classmethod
    def classify_gesture(cls, landmarks):
        """
        landmarks: list of 21 dicts with 'x', 'y', 'z' normalized coordinates.
        Returns: { 'sign': str, 'type': str, 'description': str, 'confidence': float }
        """
        if not landmarks or len(landmarks) < 21:
            return {"sign": "", "type": "none", "description": "No hand detected", "confidence": 0.0}

        # Key landmark points
        wrist = landmarks[0]
        thumb_cmc, thumb_mcp, thumb_ip, thumb_tip = landmarks[1], landmarks[2], landmarks[3], landmarks[4]
        index_mcp, index_pip, index_dip, index_tip = landmarks[5], landmarks[6], landmarks[7], landmarks[8]
        middle_mcp, middle_pip, middle_dip, middle_tip = landmarks[9], landmarks[10], landmarks[11], landmarks[12]
        ring_mcp, ring_pip, ring_dip, ring_tip = landmarks[13], landmarks[14], landmarks[15], landmarks[16]
        pinky_mcp, pinky_pip, pinky_dip, pinky_tip = landmarks[17], landmarks[18], landmarks[19], landmarks[20]

        # 1. Determine Finger States (UP vs DOWN)
        # Note: in normalized image coordinates, y=0 is top, y=1 is bottom.
        # So fingertip is extended (UP) when fingertip.y < pip.y (smaller y = higher on screen).
        is_index_up = index_tip['y'] < index_pip['y']
        is_middle_up = middle_tip['y'] < middle_pip['y']
        is_ring_up = ring_tip['y'] < ring_pip['y']
        is_pinky_up = pinky_tip['y'] < pinky_pip['y']

        # Thumb extension: check distance from thumb tip to wrist vs thumb mcp to wrist
        dist_thumb_tip_wrist = cls.euclidean_distance(thumb_tip, wrist)
        dist_thumb_mcp_wrist = cls.euclidean_distance(thumb_mcp, wrist)
        dist_thumb_tip_index_mcp = cls.euclidean_distance(thumb_tip, index_mcp)
        is_thumb_up = thumb_tip['y'] < thumb_mcp['y'] and dist_thumb_tip_wrist > dist_thumb_mcp_wrist * 1.15

        # Thumb horizontally extended outward
        is_thumb_out = abs(thumb_tip['x'] - index_mcp['x']) > 0.12

        # Distances between fingertips and thumb tip
        dist_thumb_index = cls.euclidean_distance(thumb_tip, index_tip)
        dist_thumb_middle = cls.euclidean_distance(thumb_tip, middle_tip)
        dist_thumb_ring = cls.euclidean_distance(thumb_tip, ring_tip)
        dist_thumb_pinky = cls.euclidean_distance(thumb_tip, pinky_tip)
        dist_index_middle = cls.euclidean_distance(index_tip, middle_tip)

        # Palm scale (wrist to middle MCP) for normalization
        palm_size = cls.euclidean_distance(wrist, middle_mcp) or 0.1

        # Normalized distances
        norm_thumb_index = dist_thumb_index / palm_size
        norm_index_middle = dist_index_middle / palm_size

        # --- GESTURE CLASSIFICATION RULES ---

        # 1. INTERVIEW PHRASES & CORE GESTURES
        
        # YES / THUMBS UP: Only thumb extended upward, all 4 fingers folded into fist
        if is_thumb_up and not is_index_up and not is_middle_up and not is_ring_up and not is_pinky_up:
            return {
                "sign": "YES",
                "type": "phrase",
                "description": "Thumbs Up — Affirmative / Yes",
                "confidence": 0.96
            }

        # NO / THUMBS DOWN: Thumb pointing downwards below wrist, fingers folded
        if thumb_tip['y'] > wrist['y'] and not is_index_up and not is_middle_up and not is_ring_up and not is_pinky_up:
            return {
                "sign": "NO",
                "type": "phrase",
                "description": "Thumbs Down — Negative / No",
                "confidence": 0.94
            }

        # HELLO / GREETINGS: All fingers fully extended and spread outward
        if is_index_up and is_middle_up and is_ring_up and is_pinky_up and is_thumb_out:
            if norm_index_middle > 0.35:
                return {
                    "sign": "HELLO",
                    "type": "phrase",
                    "description": "Open Hand Wave — Hello / Greetings",
                    "confidence": 0.95
                }
            else:
                return {
                    "sign": "B",
                    "type": "alphabet",
                    "description": "Letter 'B' — 4 fingers up together",
                    "confidence": 0.93
                }

        # THANK YOU / I LOVE YOU (ILY Sign): Thumb, Index, and Pinky UP; Middle and Ring folded
        if is_thumb_out and is_index_up and not is_middle_up and not is_ring_up and is_pinky_up:
            return {
                "sign": "THANK YOU",
                "type": "phrase",
                "description": "Thumb, Index, Pinky extended — Thank you / Appreciated",
                "confidence": 0.95
            }

        # OK / CONFIRMED / Letter F: Index tip touches Thumb tip forming circle, other 3 fingers UP
        if norm_thumb_index < 0.35 and is_middle_up and is_ring_up and is_pinky_up:
            return {
                "sign": "OK",
                "type": "phrase",
                "description": "OK Gesture / Letter 'F' — Confirmed / Understood",
                "confidence": 0.96
            }

        # VICTORY / LETTER 'V': Index and Middle UP, Ring and Pinky folded
        if is_index_up and is_middle_up and not is_ring_up and not is_pinky_up:
            # If fingers are separated, it's 'V'
            if norm_index_middle > 0.2:
                return {
                    "sign": "V",
                    "type": "alphabet",
                    "description": "Letter 'V' / Number 2 (Index & Middle UP)",
                    "confidence": 0.97
                }
            else:
                return {
                    "sign": "U",
                    "type": "alphabet",
                    "description": "Letter 'U' (Index & Middle UP together)",
                    "confidence": 0.92
                }

        # LETTER 'W' / NUMBER 3: Index, Middle, Ring UP; Pinky and Thumb folded
        if is_index_up and is_middle_up and is_ring_up and not is_pinky_up:
            return {
                "sign": "W",
                "type": "alphabet",
                "description": "Letter 'W' / Number 3 (Index, Middle, Ring UP)",
                "confidence": 0.95
            }

        # LETTER 'L': Index UP and Thumb extended horizontally at 90 deg; Middle, Ring, Pinky folded
        if is_index_up and is_thumb_out and not is_middle_up and not is_ring_up and not is_pinky_up:
            return {
                "sign": "L",
                "type": "alphabet",
                "description": "Letter 'L' (Index UP, Thumb Out)",
                "confidence": 0.98
            }

        # LETTER 'Y': Thumb and Pinky extended outward; Index, Middle, Ring folded
        if is_thumb_out and not is_index_up and not is_middle_up and not is_ring_up and is_pinky_up:
            return {
                "sign": "Y",
                "type": "alphabet",
                "description": "Letter 'Y' (Thumb & Pinky extended)",
                "confidence": 0.96
            }

        # LETTER 'I': Pinky UP only; Thumb, Index, Middle, Ring folded
        if not is_index_up and not is_middle_up and not is_ring_up and is_pinky_up and not is_thumb_out:
            return {
                "sign": "I",
                "type": "alphabet",
                "description": "Letter 'I' (Pinky UP)",
                "confidence": 0.97
            }

        # LETTER 'D': Index UP only; Thumb touches middle, ring, pinky tips
        if is_index_up and not is_middle_up and not is_ring_up and not is_pinky_up and not is_thumb_out:
            return {
                "sign": "D",
                "type": "alphabet",
                "description": "Letter 'D' / Number 1 (Index finger pointing UP)",
                "confidence": 0.96
            }

        # LETTER 'C': Fingers curved in a 'C' arc (tips not fully up, forming arc)
        if 0.3 < norm_thumb_index < 0.7 and not is_index_up and not is_middle_up:
            if index_tip['x'] > thumb_tip['x']: # curvature check
                return {
                    "sign": "C",
                    "type": "alphabet",
                    "description": "Letter 'C' (Curved hand arc)",
                    "confidence": 0.88
                }

        # LETTER 'A' / READY: Fist with thumb placed beside index knuckle
        if not is_index_up and not is_middle_up and not is_ring_up and not is_pinky_up:
            if thumb_tip['y'] < index_pip['y']:
                return {
                    "sign": "A",
                    "type": "alphabet",
                    "description": "Letter 'A' — Closed fist with upright thumb",
                    "confidence": 0.91
                }
            else:
                return {
                    "sign": "READY",
                    "type": "phrase",
                    "description": "Fist gesture — Ready to begin",
                    "confidence": 0.89
                }

        # 4 FINGERS UP (Number 4): All 4 fingers up, thumb folded into palm
        if is_index_up and is_middle_up and is_ring_up and is_pinky_up and not is_thumb_out:
            return {
                "sign": "4",
                "type": "number",
                "description": "Number 4 (All 4 fingers UP)",
                "confidence": 0.93
            }

        # Default fallback
        return {
            "sign": "DETECTING",
            "type": "tracking",
            "description": "Hand detected, hold gesture steady",
            "confidence": 0.60
        }

sign_engine = SignLanguageEngine()
