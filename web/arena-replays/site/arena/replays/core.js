/* Pure replay logic, also loaded by the exhaustive exported-record tests. */
(function (global) {
  'use strict';
  const seats = 'NESW', suits = 'SHDC', ranks = '23456789TJQKA';
  function initialHands(board) {
    return board.hands.map(hand => hand.split('.').flatMap((cards, i) => [...cards].map(rank => suits[i] + rank)));
  }
  function winner(trick, trump) {
    const lead = trick[0].card[0];
    const power = c => (c[0] === trump ? 30 : c[0] === lead ? 15 : 0) + ranks.indexOf(c[1]);
    return trick.reduce((best, play) => power(play.card) > power(best.card) ? play : best).seat;
  }
  function replay(board, table, ply) {
    const hands = initialHands(board), tricks = [0, 0], history = [];
    let turn = seats[(seats.indexOf(board.declarer) + 1) % 4], trick = [], shown = [];
    const trump = board.contract[1];
    for (let i = 0; i < ply; i++) {
      if (trick.length === 4) trick = [];
      const code = table.plays[i], seat = code[0], card = code.slice(1), si = seats.indexOf(seat);
      if (seat !== turn) throw Error('Invalid play order at card ' + (i + 1));
      if (!hands[si].includes(card)) throw Error('Card is absent from hand: ' + code);
      if (trick.length && card[0] !== trick[0].card[0] && hands[si].some(c => c[0] === trick[0].card[0])) throw Error('Failure to follow suit');
      hands[si].splice(hands[si].indexOf(card), 1);
      trick.push({seat, card}); shown = trick.slice();
      if (trick.length === 4) {
        turn = winner(trick, trump); tricks[seats.indexOf(turn) % 2]++;
        history.push({plays: trick.slice(), winner: turn});
      } else turn = seats[(si + 1) % 4];
    }
    return {hands, tricks, history, shown, next: ply < 52 ? turn : null,
      last: ply ? table.plays[ply - 1] : null, finishedTrick: ply > 0 && ply % 4 === 0};
  }
  function firstDifference(a, b) { const i = a.findIndex((x, i) => x !== b[i]); return i < 0 ? null : i; }
  global.BridgeReplay = {seats, suits, ranks, initialHands, winner, replay, firstDifference};
  if (typeof module !== 'undefined') module.exports = global.BridgeReplay;
})(typeof window !== 'undefined' ? window : globalThis);
