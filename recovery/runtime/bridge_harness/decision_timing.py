"""Wall-clock decision timing from root games, with explicit actor attribution."""
import math


def canonical(bot):
    return {'P':'4p','Q':'4b','BEN':'ben'}.get(bot,bot)


def merge(*summaries):
    out={'schema':'arena-decision-timing-v1','by_bot':{},'missing_timing_decisions':0}
    for summary in summaries:
        if not summary:continue
        out['missing_timing_decisions']+=summary.get('missing_timing_decisions',0)
        for key,data in summary.get('by_bot',{}).items():
            bot=out['by_bot'].setdefault(canonical(key),{'decisions':0,'total_seconds':0.,'forced_decisions':0,
                'opening_lead':{'decisions':0,'total_seconds':0.},'play':{'decisions':0,'total_seconds':0.}})
            for field in ('decisions','total_seconds','forced_decisions'):bot[field]+=data.get(field,0)
            for phase in ('opening_lead','play'):
                for field in ('decisions','total_seconds'):bot[phase][field]+=data.get(phase,{}).get(field,0)
    for bot in out['by_bot'].values():
        for data in (bot,bot['opening_lead'],bot['play']):
            data['mean_seconds']=data['total_seconds']/data['decisions'] if data['decisions'] else None
    return out


def from_game(game,actor_bots):
    out=merge()
    if not game.get('tables'):return out
    # Table zero is the actually played mainline; the remaining tables are audits.
    for action in game['tables'][0]['actions']:
        if any(action.get(k) for k in ('replayed_prefix','counterfactual_forced','fixed_opening_lead')):continue
        if 'seconds' not in action:
            out['missing_timing_decisions']+=1;continue
        seconds=action['seconds']
        if isinstance(seconds,bool) or not isinstance(seconds,(int,float)) or not math.isfinite(seconds) or seconds<0:
            raise ValueError('Invalid decision duration')
        key=canonical(actor_bots[action['player']])
        bot=out['by_bot'].setdefault(key,{'decisions':0,'total_seconds':0.,'forced_decisions':0,
            'opening_lead':{'decisions':0,'total_seconds':0.},'play':{'decisions':0,'total_seconds':0.}})
        bot['decisions']+=1;bot['total_seconds']+=seconds;bot['forced_decisions']+=int(bool(action.get('forced')))
        phase='opening_lead' if action['ply']==0 else 'play'
        bot[phase]['decisions']+=1;bot[phase]['total_seconds']+=seconds
    return merge(out)


def from_record(record):
    pair=record['pair'];pair=pair.split('~') if '~' in pair else list(pair)
    roles={'candidate':pair[0],'environment':pair[1],'opponent':pair[1]}
    keys=dict.fromkeys(key for regime in record['regimes'].values() for key in regime['tables'])
    return merge(*(from_game(record['unique_tables'][key],roles) for key in keys))
