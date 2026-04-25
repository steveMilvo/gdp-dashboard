import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'mock_repository.dart';

/// Single mock repo per app process. Phase 1 step 7 swaps this provider for a
/// `FirestoreRepository` (interface-compatible) without touching the screens.
final palenggoRepositoryProvider = Provider<MockPalengGoRepository>((ref) {
  return MockPalengGoRepository();
});
