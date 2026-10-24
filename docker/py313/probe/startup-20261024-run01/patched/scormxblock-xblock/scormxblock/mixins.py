# -*- coding: utf-8 -*-


from xblock.scorable import ScorableXBlockMixin as DefaultScorableXBlockMixin

class ScorableXBlockMixin(DefaultScorableXBlockMixin):

    def max_score(self):
        raise NotImplementedError
