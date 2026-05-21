import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'region_config.dart';

/// Active region. PH today; override at app entry to expand into ID/TH/VN/MY.
final regionConfigProvider = Provider<RegionConfig>((ref) {
  return RegionConfig.philippines;
});
