import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:palenggo_shared/palenggo_shared.dart';
import 'package:uuid/uuid.dart';

/// Phase 1 step 3 (spec §12): camera (simulated) → Cloud Vision detect →
/// merchant confirms/corrects → set price + qty → category-specific food
/// safety checklist → post live.
class MerchantHomeScreen extends ConsumerStatefulWidget {
  const MerchantHomeScreen({super.key});

  @override
  ConsumerState<MerchantHomeScreen> createState() =>
      _MerchantHomeScreenState();
}

class _MerchantHomeScreenState extends ConsumerState<MerchantHomeScreen> {
  final _productNameController = TextEditingController(text: 'Bangus');
  final _priceController = TextEditingController(text: '190');
  final _qtyController = TextEditingController(text: '20');
  FoodHandlingCategory _category = FoodHandlingCategory.rawFish;
  String _aiMessage =
      'Camera ready. Tap Detect Produce to simulate Cloud Vision.';

  @override
  void dispose() {
    _productNameController.dispose();
    _priceController.dispose();
    _qtyController.dispose();
    super.dispose();
  }

  void _runVisionDetectionStub() {
    setState(() {
      _productNameController.text = 'Bangus';
      _priceController.text = '190';
      _category = FoodHandlingCategory.rawFish;
      _aiMessage = 'Bangus detected — Milkfish. '
          'Market average today: ₱185/kg.';
    });
  }

  void _post() {
    final repo = ref.read(palenggoRepositoryProvider);
    final product = Product(
      id: const Uuid().v4(),
      stallId: 'stall_47',
      name: _productNameController.text,
      category: 'fish',
      aiDetectedName: 'Milkfish / Bangus',
      aiConfidenceScore: 0.91,
      pricePerUnit: double.tryParse(_priceController.text) ?? 0,
      unit: 'kg',
      quantityAvailable: double.tryParse(_qtyController.text) ?? 0,
      foodHandlingCategory: _category,
    );
    repo.postProduct(product);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('${product.name} posted live')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final safety = ruleFor(_category);
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
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    "Today's stall post",
                    style: TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(_aiMessage),
                  const SizedBox(height: 12),
                  FilledButton.icon(
                    onPressed: _runVisionDetectionStub,
                    icon: const Icon(Icons.camera_alt),
                    label: const Text('Detect Produce'),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _productNameController,
            decoration: const InputDecoration(labelText: 'Product name'),
          ),
          TextField(
            controller: _priceController,
            keyboardType: TextInputType.number,
            decoration:
                const InputDecoration(labelText: 'Price per kg / unit'),
          ),
          TextField(
            controller: _qtyController,
            keyboardType: TextInputType.number,
            decoration:
                const InputDecoration(labelText: 'Quantity available'),
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<FoodHandlingCategory>(
            value: _category,
            decoration:
                const InputDecoration(labelText: 'Food handling category'),
            items: FoodHandlingCategory.values
                .map(
                  (c) => DropdownMenuItem(
                    value: c,
                    child: Text(c.name),
                  ),
                )
                .toList(),
            onChanged: (value) =>
                setState(() => _category = value ?? _category),
          ),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    safety.title,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  Text(
                    'Max delivery: ${safety.maxDeliveryMinutes} min',
                    style: TextStyle(color: Theme.of(context).hintColor),
                  ),
                  const SizedBox(height: 4),
                  ...safety.checklist.map(
                    (item) => CheckboxListTile(
                      value: true,
                      onChanged: (_) {},
                      title: Text(item),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: _post,
            child: const Text('Post Product Live'),
          ),
        ],
      ),
    );
  }
}
