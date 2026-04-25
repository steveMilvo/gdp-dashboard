import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:palenggo_shared/palenggo_shared.dart';

import 'firebase_options.dart';
import 'screens/customer_home_screen.dart';

Future<void> main() async {
  await bootstrapFirebase(options: DefaultFirebaseOptions.currentPlatform);
  runApp(const ProviderScope(child: _CustomerApp()));
}

class _CustomerApp extends ConsumerWidget {
  const _CustomerApp();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp(
      title: 'PalengGo',
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
          ? const PhoneOtpScreen(appLabel: 'Customer')
          : const CustomerHomeScreen(),
    );
  }
}
