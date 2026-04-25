import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:palenggo_shared/palenggo_shared.dart';

import 'firebase_options.dart';

Future<void> main() async {
  await bootstrapFirebase(options: DefaultFirebaseOptions.currentPlatform);
  runApp(const ProviderScope(child: _MerchantApp()));
}

class _MerchantApp extends ConsumerWidget {
  const _MerchantApp();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp(
      title: 'PalengGo Merchant',
      debugShowCheckedModeBanner: false,
      theme: PalengGoTheme.light(),
      home: const _AuthGate(),
    );
  }
}

class _AuthGate extends ConsumerWidget {
  const _AuthGate();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authStateProvider);
    return auth.when(
      loading: () => const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      ),
      error: (e, _) => Scaffold(body: Center(child: Text('$e'))),
      data: (user) => user == null
          ? const PhoneOtpScreen(appLabel: 'Merchant')
          : const _MerchantHomePlaceholder(),
    );
  }
}

class _MerchantHomePlaceholder extends ConsumerWidget {
  const _MerchantHomePlaceholder();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('PalengGo Merchant'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => ref.read(authRepositoryProvider).signOut(),
          ),
        ],
      ),
      // Phase 1 next step: replace this body with camera → Vision AI → product
      // posting flow. See spec §12 Phase 1, step 3.
      body: const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text(
            'Signed in. Camera + Vision AI product posting comes next.',
            textAlign: TextAlign.center,
          ),
        ),
      ),
    );
  }
}
