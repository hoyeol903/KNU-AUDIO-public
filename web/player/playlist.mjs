export const ORDER = ['greeting', 'weather', 'notice', 'meal', 'events', 'outro'];

export function requiredChannels(manifest, departmentId) {
  const department = manifest.departments.find(d => d.id === departmentId);
  return manifest.channels.filter(c => c.required === 'all' ||
    (c.department_ids.length ? c.department_ids.includes(departmentId) :
      Array.isArray(c.required) && department && c.required.includes(department.name))).map(c => c.id);
}

export function selectPlaylist(manifest, selectedIds, excludedNotices = []) {
  const selected = new Set(selectedIds), excluded = new Set(excludedNotices);
  const notices = manifest.segments.filter(s => s.kind === 'notice' && !excluded.has(s.id) &&
    s.channel_ids.some(id => selected.has(id))).sort((a, b) =>
      (a.dday ?? Infinity) - (b.dday ?? Infinity) || a.title.localeCompare(b.title, 'ko'));
  const meals = manifest.segments.filter(s => s.kind === 'meal' && s.channel_ids.some(id => selected.has(id)));
  return [
    ...manifest.segments.filter(s => ['greeting', 'weather'].includes(s.kind)),
    ...(notices.length ? notices : manifest.segments.filter(s => s.kind === 'empty_notices')),
    ...(meals.length ? meals : manifest.segments.filter(s => s.kind === 'empty_meals')),
    ...manifest.segments.filter(s => ['events', 'outro'].includes(s.kind)),
  ];
}
