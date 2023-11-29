# -*- coding: utf-8 -*-

import json

from app.misc import JSONEncoder
from app.rewards.claimable_rewards import get_voter_claimable_rewards

from .model import BribeReward, EmissionReward, FeeReward  # noqa


class Rewards(object):
    """
    Rewards endpoint.
    """

    def on_get(self, req, resp):
        token_id = req.get_param("token_id")
        return json.dumps(
            dict(
                data=get_voter_claimable_rewards(int(token_id)),
                cls=JSONEncoder,
            )
        )
