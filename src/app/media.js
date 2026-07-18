import { PLANNER_API_URL } from './plannerData';

export const MAX_TRIP_MEDIA = 5;
export const MEDIA_ACCEPT = 'image/jpeg,image/png,image/webp,image/gif,video/mp4,video/webm,video/quicktime';

export function resolveMediaUrl(media) {
  if (!media) return '';
  if (media.preview_url) return media.preview_url;
  if (!media.url) return '';
  return media.url.startsWith('http') || media.url.startsWith('data:') || media.url.startsWith('blob:')
    ? media.url
    : `${PLANNER_API_URL}${media.url}`;
}

export function isVideoMedia(media) {
  return media?.type?.startsWith('video/');
}
