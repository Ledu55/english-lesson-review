// Runs on any www.cambly.com page while logged in. Returns the user id and finished lessons.
async () => {
  const me = await (await fetch('/api/users/current?scrub=true')).json().catch(() => null);
  const user = me && (me.result || me);
  if (!user || !user.userId) return { error: 'not_logged_in' };
  const r = await fetch('/api/lessons_v2?studentId=' + user.userId + '&viewAs=student');
  if (!r.ok) return { error: 'lessons_http_' + r.status };
  const list = ((await r.json()).result || []).filter(l => l.state === 'done');
  const date = d => d && typeof d === 'object' ? d.$date : d;
  return {
    userId: user.userId,
    lessons: list.map(l => ({
      id: l.id || (l._id && l._id.$oid),
      start: date(l.startedAt) || date(l.scheduledStartAt),
      minutes: l.scheduledMinutes || null,
    })),
  };
}
