"""Small standalone ownership transformer; all features are public pre-action data."""
from dataclasses import asdict
import numpy as np


def encode(observation):
    from .belief_capacity import encode_play
    from .training import input_tensors
    x, support = encode_play(observation)
    a = input_tensors(asdict(observation))
    order = (np.arange(4) + observation.controller) % 4
    known, played = a['known'][order].T, a['played'][order].T
    positions = np.zeros(52, np.float32)
    hc = np.full(52, 52, np.int64)
    hs = np.full(52, 4, np.int64)
    for i, (s, c) in enumerate(observation.history):
        positions[c] = (i+1)/52
        hc[i], hs[i] = c, (s-observation.controller) % 4
    # Known ownership, played ownership, order, support, legal moves, own original hand.
    cards = np.concatenate([known, played, positions[:, None], support,
                            a['legal'][:, None], x['state'][:52, None]], axis=1).astype(np.float32)
    context = np.concatenate([x['state'][52:], x['play'][468:]]).astype(np.float32)
    return dict(cards=cards, context=context, calls=x['calls'].astype(np.int64),
                seats=x['seats'].astype(np.int64), history_cards=hc, history_seats=hs,
                support=support), x


def make_model(width=128, layers=2, heads=4, dropout=.1):
    import torch
    from torch import nn

    class OwnershipTransformer(nn.Module):
        def __init__(self):
            super().__init__()
            self.card_features = nn.Linear(15, width)
            self.suit = nn.Embedding(4, width)
            self.rank = nn.Embedding(13, width)
            self.call = nn.Embedding(39, width, padding_idx=0)
            self.seat = nn.Embedding(5, width, padding_idx=4)
            self.auction_position = nn.Embedding(64, width)
            self.play_position = nn.Embedding(52, width)
            self.kind = nn.Embedding(4, width)
            self.context = nn.Linear(67, width)
            self.blocks = nn.ModuleList([nn.TransformerEncoderLayer(
                width, heads, width*4, dropout, activation='gelu',
                batch_first=True, norm_first=True) for _ in range(layers)])
            self.norm = nn.LayerNorm(width)
            self.head = nn.Linear(width, 4)
            self.dropout = nn.Dropout(dropout)

        def forward(self, x):
            device = x['cards'].device
            c = torch.arange(52, device=device)
            identities = self.suit(c//13) + self.rank(c%13)
            cards = self.card_features(x['cards']) + identities + self.kind.weight[0]
            na = max(1, int((x['calls'] != 0).sum(1).max()))
            nh = max(1, int((x['history_cards'] != 52).sum(1).max()))
            calls, seats = x['calls'][:, :na], x['seats'][:, :na]
            hc, hs = x['history_cards'][:, :nh], x['history_seats'][:, :nh]
            auction = self.call(calls) + self.seat(seats) + self.auction_position(
                torch.arange(na, device=device)) + self.kind.weight[1]
            history = identities[hc.clamp(max=51)] + self.seat(hs) + self.play_position(
                torch.arange(nh, device=device)) + self.kind.weight[2]
            context = self.context(x['context'])[:, None] + self.kind.weight[3]
            h = self.dropout(torch.cat([cards, context, auction, history], 1))
            padding = torch.cat([torch.zeros((len(calls), 53), dtype=torch.bool, device=device),
                                 calls == 0, hc == 52], 1)
            for block in self.blocks:
                h = block(h, src_key_padding_mask=padding)
            return self.head(self.norm(h[:, :52]))

    return OwnershipTransformer()


INPUTS = ('cards', 'context', 'calls', 'seats', 'history_cards', 'history_seats', 'support')


def torch_batch(arrays, indices):
    import torch
    return {k: torch.from_numpy(arrays[k][indices]) for k in INPUTS}


def per_position_loss(logits, target, support, mask):
    import torch.nn.functional as F
    masked = logits.masked_fill(~support, -1e9)
    ce = F.cross_entropy(masked.transpose(1, 2), target.long(), reduction='none')
    return (ce*mask).sum(1)/mask.sum(1).clamp(min=1)


class Weights:
    def __init__(self, path):
        import torch
        checkpoint = torch.load(path, map_location='cpu', weights_only=False)
        self.model = make_model(**checkpoint['architecture'])
        self.model.load_state_dict(checkpoint['model'])
        self.model.eval()

    def logits(self, observation):
        import torch
        x, _ = encode(observation)
        with torch.inference_mode():
            relative = self.model({k: torch.from_numpy(v[None]) for k, v in x.items()})[0].numpy()
        return relative[:, [(s-observation.controller) % 4 for s in range(4)]]
