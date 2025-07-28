package org.jmc.models;

import org.jmc.BlockData;
import org.jmc.registry.NamespaceID;
import org.jmc.threading.ChunkProcessor;
import org.jmc.threading.ThreadChunkDeligate;


/**
 * Dummy model that doesn't generate any geometry.
 */
public class None extends BlockModel
{

	@Override
	public void addModel(ChunkProcessor obj, ThreadChunkDeligate chunks, int x, int y, int z, BlockData data, NamespaceID biome)
	{
	}

}
